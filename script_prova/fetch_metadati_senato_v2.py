#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "pyarrow", "requests", "duckdb"]
# ///
"""
fetch_metadati_senato_v2.py — Extends fetch_metadati_senato with signatory and
parliamentary-group data for DDL (Leg13–19).

Adds per-DDL:
  - First signatory (senator URI, name, parliamentary group in that legislature)
  - Co-signatories (senator URI, name, signing/withdrawal dates, group)

Outputs:
  - data/meta/atti_senato_v2.parquet    — extended DDL schema
  - data/meta/firmatari_senato.parquet  — one row per signatory × DDL
  - data/meta/coverage_senato_v2.parquet
  - data/meta/fetch_log_senato_v2.json

Key technical notes (confirmed empirically 2026-05-29):
  - osr:primoFirmatario is xsd:string "1", not boolean
  - osr:senatore present on ~30% of osr:Iniziativa — expected data gap
  - osr:legislatura is NOT a property of osr:Senatore; navigate via osr:Iniziativa
  - Parliamentary group chain: ocd:aderisce → ocd:adesioneGruppo → osr:gruppo
  - adesioneGruppo blank nodes are duplicated — DISTINCT + Python dedup required
  - FILTER IN batches capped at 25 URIs: endpoint 403s above ~2100-char URLs (confirmed 2026-05-29)

Usage:
  uv run script_prova/fetch_metadati_senato_v2.py --legs 17
  uv run script_prova/fetch_metadati_senato_v2.py --force
  uv run script_prova/fetch_metadati_senato_v2.py --no-emend --no-firmatari
  uv run script_prova/fetch_metadati_senato_v2.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    import duckdb as _duckdb
    HAS_PARQUET = True
except ImportError:
    _duckdb = None  # type: ignore[assignment]
    HAS_PARQUET = False

# ---------------------------------------------------------------------------
# Parquet helper
# ---------------------------------------------------------------------------

def write_parquet(df: "pd.DataFrame", path: "Path") -> None:
    """Write DataFrame to Parquet via DuckDB COPY TO.

    DuckDB writes Parquet format 1.0, readable by all pyarrow versions.
    pandas.to_parquet() with pyarrow >= 23 defaults to format 2.6, incompatible
    with pyarrow < 24 (confirmed 2026-05-27).
    """
    con = _duckdb.connect()
    con.register("_df", df)
    con.execute(f"COPY _df TO '{path}' (FORMAT PARQUET)")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SPARQL_ENDPOINT = "https://dati.senato.it/sparql"
ALL_LEGS        = list(range(13, 20))
CHUNK           = 1000
MAX_RETRY       = 3
RETRY_WAIT      = 5
SLEEP_BETWEEN   = 1.0
# Max URIs per FILTER IN block.
# The Senato endpoint returns HTTP 403 when URL length exceeds ~2100 chars.
# At ~65 chars/URI (URL-encoded), 25 URIs ≈ 1625 chars — safe margin below limit.
# (31 URIs = 2063 chars works; 32 URIs = 2119 chars fails — confirmed 2026-05-29)
URI_BATCH_SIZE  = 25
DATA_DIR        = Path("data")
META_DIR        = DATA_DIR / "meta"

HEADERS = {
    "Accept":     "application/sparql-results+json",
    "User-Agent": "iter-legis-dataset/1.0 (tesi; giacomo.sperti@uniXX.it)",
}

# ---------------------------------------------------------------------------
# SPARQL helpers
# ---------------------------------------------------------------------------

def sparql(query: str, timeout: int = 60) -> list[dict]:
    """Execute a SPARQL query and return bindings as a list of dicts.

    Retries up to MAX_RETRY times on network/server errors.
    """
    params = urllib.parse.urlencode({
        "query":  query,
        "format": "application/sparql-results+json",
    })
    url = f"{SPARQL_ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers=HEADERS)

    for attempt in range(1, MAX_RETRY + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
                return data.get("results", {}).get("bindings", [])
        except urllib.error.HTTPError as e:
            print(f"      HTTP {e.code} (attempt {attempt}/{MAX_RETRY})")
        except Exception as e:
            print(f"      Error: {e} (attempt {attempt}/{MAX_RETRY})")
        if attempt < MAX_RETRY:
            time.sleep(RETRY_WAIT)
    return []


def val(binding: dict, key: str) -> str | None:
    """Extract a string value from a SPARQL binding, or None if absent."""
    entry = binding.get(key)
    return entry["value"] if entry else None


def uris_to_filter_in(uris: list[str]) -> str:
    """Format a list of URIs for use in a SPARQL FILTER IN expression.

    The Senato endpoint (Virtuoso) does not support the VALUES keyword (SPARQL 1.1).
    FILTER(?s IN (...)) is the supported alternative (confirmed 2026-05-29).
    """
    return ", ".join(f"<{u}>" for u in uris)


def sparql_paginated(query_template: str, leg: int) -> list[dict]:
    """LIMIT/OFFSET pagination for queries with moderate result sets."""
    all_rows: list[dict] = []
    offset = 0
    while True:
        q = query_template.format(leg=leg, limit=CHUNK, offset=offset)
        rows = sparql(q)
        if not rows:
            break
        all_rows.extend(rows)
        print(f"      offset={offset:>6}  +{len(rows):>4}  total={len(all_rows)}")
        if len(rows) < CHUNK:
            break
        offset += CHUNK
        time.sleep(SLEEP_BETWEEN)
    return all_rows


def sparql_keyset_ddl(leg: int) -> list[dict]:
    """Keyset pagination for DDL_QUERY, filtering on osr:idFase.

    Bypasses the Virtuoso ResultSetMaxRows cap by issuing fresh queries
    with FILTER(?id_fase > {last_id}) instead of incrementing OFFSET.
    """
    all_rows: list[dict] = []
    last_id  = 0
    page     = 0
    while True:
        page += 1
        q = DDL_QUERY.format(leg=leg, last_id=last_id, limit=CHUNK)
        rows = sparql(q)
        if not rows:
            break
        all_rows.extend(rows)

        ids = [int(val(r, "id_fase")) for r in rows if val(r, "id_fase")]
        if not ids:
            print("      Warning: no id_fase on page — stopping.")
            break
        last_id = max(ids)
        print(f"      page={page:>3}  last_id={last_id:>8}  +{len(rows):>4}  total={len(all_rows)}")

        if len(rows) < CHUNK:
            break
        time.sleep(SLEEP_BETWEEN)
    return all_rows


def sparql_keyset_firmatari(leg: int) -> list[dict]:
    """Keyset pagination for FIRMATARI_QUERY, filtering on the DDL's osr:idFase.

    Multiple rows share the same id_fase (one per firmatario per DDL).
    To avoid splitting a DDL's firmatari across page boundaries when a full
    page ends mid-DDL, the cursor advances to the second-to-last distinct
    id_fase on each full page. Python-level dedup handles any overlap.
    """
    all_rows: list[dict] = []
    last_id  = 0
    page     = 0
    while True:
        page += 1
        q = FIRMATARI_QUERY.format(leg=leg, last_id=last_id, limit=CHUNK)
        rows = sparql(q)
        if not rows:
            break
        all_rows.extend(rows)

        ids = [int(val(r, "id_fase")) for r in rows if val(r, "id_fase")]
        if not ids:
            print("      Warning: no id_fase on page — stopping.")
            break
        print(f"      page={page:>3}  last_id={last_id:>8}  +{len(rows):>4}  total={len(all_rows)}")

        if len(rows) < CHUNK:
            break

        # Advance to second-to-last distinct id_fase to avoid splitting multi-row DDLs.
        # The last group is re-fetched on the next page; Python dedup removes duplicates.
        distinct_ids = sorted(set(ids))
        if len(distinct_ids) >= 2:
            last_id = distinct_ids[-2]
        else:
            # Entire page shares one id_fase (DDL with 1000+ signatories — extremely unlikely)
            last_id = distinct_ids[0]
        time.sleep(SLEEP_BETWEEN)
    return all_rows


# ---------------------------------------------------------------------------
# SPARQL queries
# ---------------------------------------------------------------------------

# DDL_QUERY — unchanged from fetch_metadati_senato.py.
#
# Keyset pagination on osr:idFase bypasses the Virtuoso ResultSetMaxRows cap.
# URI pattern: http://dati.senato.it/ddl/{idFase}
# osr:descrIniziativa stores the presentatore text for the whole DDL.
DDL_QUERY = """
PREFIX osr: <http://dati.senato.it/osr/>

SELECT DISTINCT
  ?ddl
  ?id_ddl
  ?id_fase
  ?numero_fase
  ?fase
  ?prog_iter
  ?ramo
  ?titolo
  ?data_presentazione
  ?stato_ddl
  ?data_stato
  ?presentato_trasmesso
  ?natura
  ?descr_iniziativa
  ?testo_presentato
  ?testo_approvato
WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:idFase ?id_fase .
  FILTER(?id_fase > {last_id})

  OPTIONAL {{ ?ddl osr:idDdl               ?id_ddl              }}
  OPTIONAL {{ ?ddl osr:numeroFase          ?numero_fase         }}
  OPTIONAL {{ ?ddl osr:fase                ?fase                }}
  OPTIONAL {{ ?ddl osr:progressivoIter     ?prog_iter           }}
  OPTIONAL {{ ?ddl osr:ramo                ?ramo                }}
  OPTIONAL {{ ?ddl osr:titolo              ?titolo              }}
  OPTIONAL {{ ?ddl osr:dataPresentazione   ?data_presentazione  }}
  OPTIONAL {{ ?ddl osr:statoDdl            ?stato_ddl           }}
  OPTIONAL {{ ?ddl osr:dataStatoDdl        ?data_stato          }}
  OPTIONAL {{ ?ddl osr:presentatoTrasmesso ?presentato_trasmesso }}
  OPTIONAL {{ ?ddl osr:natura              ?natura              }}
  OPTIONAL {{ ?ddl osr:descrIniziativa     ?descr_iniziativa    }}
  OPTIONAL {{ ?ddl osr:testoPresentato     ?testo_presentato    }}
  OPTIONAL {{ ?ddl osr:testoApprovato      ?testo_approvato     }}
}}
ORDER BY ?id_fase
LIMIT {limit}
"""

# FIRMATARI_QUERY — one row per osr:Iniziativa per DDL.
#
# osr:primoFirmatario is xsd:string "1" (not boolean) — confirmed 2026-05-29.
# osr:senatore is OPTIONAL; present on ~30% of Iniziativa — expected data gap.
# osr:tipoIniziativa is required (always populated): "Parlamentare", "Governativa",
# "Regionale", "Popolare", "CNEL".
# Keyset on DDL's osr:idFase; multiple rows per id_fase (one per firmatario).
FIRMATARI_QUERY = """
PREFIX osr: <http://dati.senato.it/osr/>

SELECT DISTINCT
  ?ddl
  ?id_fase
  ?iniz
  ?tipo_iniziativa
  ?primo_firmatario
  ?s_uri
  ?presentatore
  ?data_firma
  ?data_ritiro
WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:idFase ?id_fase ;
       osr:iniziativa ?iniz .
  FILTER(?id_fase > {last_id})

  ?iniz osr:tipoIniziativa ?tipo_iniziativa .
  OPTIONAL {{ ?iniz osr:primoFirmatario   ?primo_firmatario }}
  OPTIONAL {{ ?iniz osr:senatore          ?s_uri            }}
  OPTIONAL {{ ?iniz osr:presentatore      ?presentatore     }}
  OPTIONAL {{ ?iniz osr:dataAggiuntaFirma ?data_firma       }}
  OPTIONAL {{ ?iniz osr:dataRitiroFirma   ?data_ritiro      }}
}}
ORDER BY ?id_fase
LIMIT {limit}
"""

# NOMI_QUERY — batch foaf name lookup for a list of senator URIs.
# {uris} is substituted with a comma-separated list of <uri> tokens for FILTER IN.
# The Senato endpoint (Virtuoso) does not support the VALUES keyword (SPARQL 1.1);
# FILTER(?s IN (...)) is the supported alternative — confirmed 2026-05-29.
NOMI_QUERY = """
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX osr: <http://dati.senato.it/osr/>

SELECT DISTINCT ?s ?nome ?cognome ?label WHERE {{
  ?s a osr:Senatore .
  OPTIONAL {{ ?s foaf:firstName ?nome    }}
  OPTIONAL {{ ?s foaf:lastName  ?cognome }}
  OPTIONAL {{ ?s rdfs:label     ?label   }}
  FILTER(?s IN ({uris}))
}}
"""

# GRUPPI_QUERY — all parliamentary group memberships for senators who signed DDL
# in a given legislature, navigated via the DDL → Iniziativa → Senatore chain.
#
# Confirmed chain (2026-05-29):
#   osr:Ddl → osr:iniziativa → osr:Iniziativa → osr:senatore → osr:Senatore
#   → ocd:aderisce → ocd:adesioneGruppo → osr:gruppo → osr:denominazione
#
# Navigating from DDL avoids FILTER IN entirely, which is necessary because:
# - VALUES (SPARQL 1.1) is not supported by this endpoint (HTTP 400)
# - FILTER IN with the full GRUPPI query body exceeds the ~2100-char URL limit
#   at as few as 25 URIs (confirmed 2026-05-29)
#
# Critical: osr:legislatura is on adesioneGruppo, NOT on osr:Senatore.
# adesioneGruppo blank nodes are duplicated — DISTINCT + Python dedup required.
# The inner FILTER selects the group name valid at the time of the membership start.
# Uses LIMIT/OFFSET pagination (Leg17 produces ~800 rows, safely under the cap).
GRUPPI_QUERY = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT DISTINCT ?s ?gruppoURI ?titoloGruppo ?titoloBreve ?carica ?adGInizio ?adGFine WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?s .
  ?s ocd:aderisce ?adG .
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura {leg} ;
       osr:gruppo      ?gruppoURI ;
       osr:carica      ?carica ;
       osr:inizio      ?adGInizio .
  OPTIONAL {{ ?adG osr:fine ?adGFine . }}

  ?gruppoURI osr:denominazione ?dn .
  ?dn osr:titolo      ?titoloGruppo ;
      osr:titoloBreve ?titoloBreve ;
      osr:inizio      ?dnInizio .
  OPTIONAL {{ ?dn osr:fine ?dnFine . }}
  FILTER(?dnInizio <= ?adGInizio &&
         (!bound(?dnFine) || ?dnFine >= ?adGInizio))
}}
ORDER BY ?s
LIMIT {limit}
OFFSET {offset}
"""

# EMEND_COUNT_QUERY and EMEND_AKN_QUERY — unchanged from fetch_metadati_senato.py.
# Catena: osr:Emendamento → osr:oggetto → osr:OggettoTrattazione → osr:relativoA → osr:Ddl
EMEND_COUNT_QUERY = """
PREFIX osr: <http://dati.senato.it/osr/>

SELECT ?ddl (COUNT(DISTINCT ?emend) AS ?n_emend)
WHERE {{
  ?emend a osr:Emendamento ;
         osr:legislatura {leg} ;
         osr:oggetto ?ogg .
  ?ogg osr:relativoA ?ddl .
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} .
}}
GROUP BY ?ddl
LIMIT {limit}
OFFSET {offset}
"""

EMEND_AKN_QUERY = """
PREFIX osr: <http://dati.senato.it/osr/>

SELECT ?ddl (COUNT(DISTINCT ?emend) AS ?n_emend_akn)
WHERE {{
  ?emend a osr:Emendamento ;
         osr:legislatura {leg} ;
         osr:oggetto ?ogg ;
         osr:URLTestoXml ?url .
  ?ogg osr:relativoA ?ddl .
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} .
}}
GROUP BY ?ddl
LIMIT {limit}
OFFSET {offset}
"""


# ---------------------------------------------------------------------------
# Fetch — base (unchanged from fetch_metadati_senato.py)
# ---------------------------------------------------------------------------

def fetch_ddl(leg: int, dry_run: bool = False) -> pd.DataFrame:
    """Fetch all DDL for a legislature with full metadata. Unchanged from v1."""
    print(f"  [DDL] Leg{leg} — main metadata")

    if dry_run:
        q = DDL_QUERY.format(leg=leg, last_id=0, limit=5)
        print(f"\n  === DDL_QUERY (dry-run, LIMIT 5) ===\n{q}\n{'='*50}")
        return pd.DataFrame()

    rows = sparql_keyset_ddl(leg)
    if not rows:
        print(f"  Warning: no DDL found for Leg{leg}")
        return pd.DataFrame()

    records = []
    for r in rows:
        uri    = val(r, "ddl") or ""
        uri_id = uri.rstrip("/").split("/")[-1]
        urn    = val(r, "testo_presentato")
        prog   = val(r, "prog_iter")

        records.append({
            "id_fase":               uri_id,
            "id_ddl_interno":        val(r, "id_ddl"),
            "id_fase_sparql":        val(r, "id_fase"),
            "uri_ddl":               uri,
            "legislatura":           leg,
            "progressivo_iter":      int(prog) if prog else None,
            "is_prima_fase":         prog == "1",
            "numero_fase":           val(r, "numero_fase"),
            "fase":                  val(r, "fase"),
            "ramo_origine":          val(r, "ramo"),
            "titolo":                val(r, "titolo"),
            "data_presentazione":    val(r, "data_presentazione"),
            "stato_ddl":             val(r, "stato_ddl"),
            "data_stato_ddl":        val(r, "data_stato"),
            "presentato_trasmesso":  val(r, "presentato_trasmesso"),
            "natura":                val(r, "natura"),
            "descr_iniziativa":      val(r, "descr_iniziativa"),
            "urn_testo_presentato":  urn,
            "has_testo_presentato":  urn is not None,
            "urn_testo_approvato":   val(r, "testo_approvato"),
            "has_testo_approvato":   val(r, "testo_approvato") is not None,
        })

    return pd.DataFrame(records)


def fetch_emend_counts(leg: int, dry_run: bool = False) -> pd.DataFrame:
    """Fetch amendment counts per DDL. Unchanged from v1."""
    print(f"  [EMD] Leg{leg} — amendment count (total)")
    if dry_run:
        return pd.DataFrame()

    rows_tot = sparql_paginated(EMEND_COUNT_QUERY, leg)
    time.sleep(SLEEP_BETWEEN)
    print(f"  [EMD] Leg{leg} — amendment count (AKN available)")
    rows_akn = sparql_paginated(EMEND_AKN_QUERY, leg)

    def parse_counts(rows: list[dict], col: str, sparql_var: str = "n_emend") -> pd.DataFrame:
        if not rows:
            return pd.DataFrame(columns=["id_fase", col])
        recs = []
        for r in rows:
            uri = val(r, "ddl") or ""
            id_fase = uri.rstrip("/").split("/")[-1]
            recs.append({"id_fase": id_fase, col: int(val(r, sparql_var) or 0)})
        return pd.DataFrame(recs)

    df_tot = parse_counts(rows_tot, "n_emendamenti",     sparql_var="n_emend")
    df_akn = parse_counts(rows_akn, "n_emendamenti_akn", sparql_var="n_emend_akn")

    if df_tot.empty and df_akn.empty:
        return pd.DataFrame(columns=["id_fase", "n_emendamenti", "n_emendamenti_akn"])
    if df_tot.empty:
        df_tot = df_akn[["id_fase"]].copy()
        df_tot["n_emendamenti"] = 0
    if df_akn.empty:
        df_akn = df_tot[["id_fase"]].copy()
        df_akn["n_emendamenti_akn"] = 0

    df = df_tot.merge(df_akn, on="id_fase", how="outer").fillna(0)
    df["n_emendamenti"]     = df["n_emendamenti"].astype(int)
    df["n_emendamenti_akn"] = df["n_emendamenti_akn"].astype(int)
    return df


# ---------------------------------------------------------------------------
# Fetch — new (firmatari, nomi, gruppi)
# ---------------------------------------------------------------------------

def fetch_firmatari(leg: int, dry_run: bool = False) -> pd.DataFrame:
    """Fetch all signatories (osr:Iniziativa) for DDL in a legislature.

    Returns one row per (DDL, Iniziativa). The nome_senatore column is
    initially populated from osr:presentatore; foaf names are resolved later
    by fetch_nomi_senatori and written back by the caller.
    """
    print(f"  [FIR] Leg{leg} — signatories")

    if dry_run:
        q = FIRMATARI_QUERY.format(leg=leg, last_id=0, limit=5)
        print(f"\n  === FIRMATARI_QUERY (dry-run, LIMIT 5) ===\n{q}\n{'='*50}")
        return pd.DataFrame()

    rows = sparql_keyset_firmatari(leg)
    if not rows:
        print(f"  Warning: no firmatari found for Leg{leg}")
        return pd.DataFrame()

    records = []
    for r in rows:
        ddl_uri = val(r, "ddl") or ""
        id_fase = ddl_uri.rstrip("/").split("/")[-1]
        pf_str  = val(r, "primo_firmatario")

        records.append({
            "id_fase":             id_fase,
            "legislatura":         leg,
            "uri_iniziativa":      val(r, "iniz"),
            # xsd:string "1" flags the first signatory (confirmed 2026-05-29)
            "is_primo_firmatario": pf_str == "1",
            "uri_senatore":        val(r, "s_uri"),
            # Populated from osr:presentatore here; overwritten with foaf by caller
            "nome_senatore":       val(r, "presentatore"),
            "tipo_iniziativa":     val(r, "tipo_iniziativa"),
            "data_firma":          val(r, "data_firma"),
            "data_ritiro_firma":   val(r, "data_ritiro"),
        })

    df = pd.DataFrame(records)
    # Dedup on natural key to handle any SPARQL DISTINCT gaps
    df = df.drop_duplicates(subset=["id_fase", "uri_iniziativa"])
    print(f"      {len(df)} signatory rows ({df['uri_senatore'].notna().sum()} with senator URI)")
    return df


def fetch_nomi_senatori(uris: list[str]) -> dict[str, tuple[str | None, str | None]]:
    """Fetch foaf:firstName / foaf:lastName for a list of senator URIs.

    Returns dict mapping uri → (nome, cognome). Batches of URI_BATCH_SIZE
    avoid HTTP 400 errors from oversized VALUES blocks.
    """
    if not uris:
        return {}

    result: dict[str, tuple[str | None, str | None]] = {}
    n_batches = -(-len(uris) // URI_BATCH_SIZE)

    for i in range(0, len(uris), URI_BATCH_SIZE):
        batch = uris[i : i + URI_BATCH_SIZE]
        q     = NOMI_QUERY.format(uris=uris_to_filter_in(batch))
        rows  = sparql(q)
        for r in rows:
            uri = val(r, "s")
            if not uri:
                continue
            nome    = val(r, "nome")
            cognome = val(r, "cognome")
            # Fall back to rdfs:label split when foaf names are absent
            if not nome and not cognome:
                label = val(r, "label") or ""
                parts = label.split(" ", 1)
                nome    = parts[0] if parts else None
                cognome = parts[1] if len(parts) > 1 else None
            result[uri] = (nome, cognome)
        batch_num = i // URI_BATCH_SIZE + 1
        print(f"      nomi batch {batch_num}/{n_batches}  resolved={len(result)}")
        time.sleep(SLEEP_BETWEEN)

    return result


def fetch_gruppi(leg: int) -> pd.DataFrame:
    """Fetch parliamentary group memberships for all DDL signatories in a legislature.

    Navigates via DDL → Iniziativa → Senatore → adesioneGruppo, avoiding the need
    for a FILTER IN batch loop. FILTER IN with the full GRUPPI query body exceeds
    the endpoint's ~2100-char URL limit at ~25 URIs (confirmed 2026-05-29).

    Returns one row per (uri_senatore, gruppo_uri, adGInizio) after deduplication
    of triplestore blank node duplicates (confirmed 2026-05-29).
    """
    print(f"  [GRP] Leg{leg} — parliamentary groups (DDL navigation)")

    all_rows: list[dict] = []
    offset = 0
    while True:
        q    = GRUPPI_QUERY.format(leg=leg, limit=CHUNK, offset=offset)
        rows = sparql(q)
        if not rows:
            break
        all_rows.extend(rows)
        print(f"      offset={offset:>6}  +{len(rows):>4}  total={len(all_rows)}")
        if len(rows) < CHUNK:
            break
        offset += CHUNK
        time.sleep(SLEEP_BETWEEN)

    if not all_rows:
        print(f"  Warning: no group data found for Leg{leg} — check DDL/Iniziativa chain")
        return pd.DataFrame()

    records = [
        {
            "uri_senatore":  val(r, "s"),
            "gruppo_uri":    val(r, "gruppoURI"),
            "gruppo_nome":   val(r, "titoloGruppo"),
            "gruppo_sigla":  val(r, "titoloBreve"),
            "carica_gruppo": val(r, "carica"),
            "adGInizio":     val(r, "adGInizio"),
            "adGFine":       val(r, "adGFine"),
        }
        for r in all_rows
    ]
    df = pd.DataFrame(records)
    # Eliminate triplestore blank node duplicates (confirmed issue 2026-05-29)
    df = df.drop_duplicates(subset=["uri_senatore", "gruppo_uri", "adGInizio"])
    return df


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def build_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate coverage statistics per (legislatura, ramo_origine)."""
    if df.empty:
        return pd.DataFrame()

    # Ensure amendment columns exist for aggregation
    for col in ["has_emendamenti", "has_emendamenti_akn", "n_emendamenti"]:
        if col not in df.columns:
            df = df.copy()
            df[col] = 0

    grp = df.groupby(["legislatura", "ramo_origine"], dropna=False)
    cov = grp.agg(
        n_ddl                  = ("id_fase",              "count"),
        n_con_testo_presentato = ("has_testo_presentato", "sum"),
        n_con_emendamenti      = ("has_emendamenti",       "sum"),
        n_con_emendamenti_akn  = ("has_emendamenti_akn",   "sum"),
        n_emendamenti_totali   = ("n_emendamenti",         "sum"),
    ).reset_index()

    if "uri_primo_firmatario" in df.columns:
        n_pf = (
            df.groupby(["legislatura", "ramo_origine"], dropna=False)["uri_primo_firmatario"]
            .apply(lambda x: int(x.notna().sum()))
            .rename("n_con_primo_firmatario")
            .reset_index()
        )
        cov = cov.merge(n_pf, on=["legislatura", "ramo_origine"], how="left")
        cov["pct_primo_firmatario"] = (cov["n_con_primo_firmatario"] / cov["n_ddl"] * 100).round(1)

    cov["pct_testo_presentato"] = (cov["n_con_testo_presentato"] / cov["n_ddl"] * 100).round(1)
    cov["pct_emendamenti_akn"]  = (cov["n_con_emendamenti_akn"]  / cov["n_ddl"] * 100).round(1)
    return cov


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_empty_firmatari_cols(df: pd.DataFrame) -> None:
    """Add null/zero signatory and group columns when --no-firmatari is set."""
    for col in [
        "tipo_iniziativa", "uri_primo_firmatario", "nome_primo_firmatario",
        "gruppo_primo_firmatario_uri", "gruppo_primo_firmatario_nome",
        "gruppo_primo_firmatario_sigla",
    ]:
        if col not in df.columns:
            df[col] = None
    for col in ["n_cofirmatari", "n_cofirmatari_totale"]:
        if col not in df.columns:
            df[col] = 0


def _print_summary(df: pd.DataFrame, leg: int, elapsed: float) -> None:
    n     = len(df)
    n_tp  = int(df["has_testo_presentato"].sum()) if "has_testo_presentato" in df.columns else 0
    n_ta  = int(df["has_testo_approvato"].sum())  if "has_testo_approvato"  in df.columns else 0
    n_em  = int(df["has_emendamenti"].sum())       if "has_emendamenti"      in df.columns else 0
    n_akn = int(df["has_emendamenti_akn"].sum())   if "has_emendamenti_akn"  in df.columns else 0
    n_pf  = int(df["uri_primo_firmatario"].notna().sum()) if "uri_primo_firmatario" in df.columns else -1
    rami  = df["ramo_origine"].value_counts().to_dict() if "ramo_origine" in df.columns else {}

    print(f"\n  OK Leg{leg}: {n} DDL in {elapsed:.1f}s")
    print(f"     Rami              : {rami}")
    print(f"     Testo presentato  : {n_tp}/{n} ({n_tp/n*100:.1f}%)")
    print(f"     Testo approvato   : {n_ta}/{n} ({n_ta/n*100:.1f}%)")
    print(f"     Con emendamenti   : {n_em}/{n} ({n_em/n*100:.1f}%)")
    print(f"     Emend. AKN        : {n_akn}/{n} ({n_akn/n*100:.1f}%)")
    if n_pf >= 0:
        print(f"     Primo firmatario  : {n_pf}/{n} ({n_pf/n*100:.1f}%)")


def _make_log_entry(df: pd.DataFrame, leg: int, elapsed: float, fetch_ts: str) -> dict:
    n    = len(df)
    n_pf = int(df["uri_primo_firmatario"].notna().sum()) if "uri_primo_firmatario" in df.columns else None
    return {
        "legislatura":        leg,
        "status":             "ok",
        "n_ddl":              n,
        "rami":               df["ramo_origine"].value_counts().to_dict() if "ramo_origine" in df.columns else {},
        "n_primo_firmatario": n_pf,
        "n_testo_presentato": int(df["has_testo_presentato"].sum()) if "has_testo_presentato" in df.columns else 0,
        "n_con_emendamenti":  int(df["has_emendamenti"].sum())      if "has_emendamenti"      in df.columns else 0,
        "elapsed_s":          round(elapsed, 1),
        "fetch_ts":           fetch_ts,
    }


def _reorder_atti_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Apply canonical column order for atti_senato_v2.parquet."""
    col_order = [
        # Identifiers
        "id_fase", "id_ddl_interno", "id_fase_sparql", "uri_ddl",
        # Legislature and iter
        "legislatura", "progressivo_iter", "is_prima_fase",
        # Numbering
        "numero_fase", "fase",
        # Descriptive metadata
        "ramo_origine", "titolo", "data_presentazione",
        "stato_ddl", "data_stato_ddl", "presentato_trasmesso", "natura",
        "descr_iniziativa",
        # Text
        "urn_testo_presentato", "has_testo_presentato",
        "urn_testo_approvato",  "has_testo_approvato",
        # Amendments
        "n_emendamenti", "n_emendamenti_akn",
        "has_emendamenti", "has_emendamenti_akn",
        # Signatories (new in v2)
        "tipo_iniziativa",
        "uri_primo_firmatario", "nome_primo_firmatario",
        "gruppo_primo_firmatario_uri", "gruppo_primo_firmatario_nome",
        "gruppo_primo_firmatario_sigla",
        "n_cofirmatari", "n_cofirmatari_totale",
        # Provenance
        "fonte", "data_fetch",
    ]
    extra = [c for c in df.columns if c not in col_order]
    if extra:
        print(f"  Info: unexpected columns: {extra}")
    return df[[c for c in col_order if c in df.columns] + extra]


def _reorder_firmatari_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Apply canonical column order for firmatari_senato.parquet."""
    col_order = [
        "id_fase", "legislatura", "uri_iniziativa",
        "is_primo_firmatario", "uri_senatore", "nome_senatore",
        "tipo_iniziativa", "data_firma", "data_ritiro_firma",
        "gruppo_uri", "gruppo_nome", "gruppo_sigla", "carica_gruppo",
    ]
    extra = [c for c in df.columns if c not in col_order]
    return df[[c for c in col_order if c in df.columns] + extra]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch DDL metadata with signatories and groups (Leg13-19)"
    )
    parser.add_argument("--legs",         type=int, nargs="+", default=ALL_LEGS)
    parser.add_argument("--force",        action="store_true",
                        help="Overwrite existing output")
    parser.add_argument("--dry-run",      action="store_true",
                        help="Print queries without executing them")
    parser.add_argument("--no-emend",     action="store_true",
                        help="Skip amendment counts (faster)")
    parser.add_argument("--no-firmatari", action="store_true",
                        help="Skip signatory and group fetch (faster)")
    args = parser.parse_args()

    META_DIR.mkdir(parents=True, exist_ok=True)
    out_atti = META_DIR / "atti_senato_v2.parquet"
    out_firm = META_DIR / "firmatari_senato.parquet"
    out_cov  = META_DIR / "coverage_senato_v2.parquet"
    out_log  = META_DIR / "fetch_log_senato_v2.json"

    # Per-legislature idempotency: load existing output, skip legs already present.
    # --force bypasses this and re-fetches all requested legs from scratch.
    existing_ddl_df:      pd.DataFrame | None = None
    existing_firm_df:     pd.DataFrame | None = None
    existing_log_entries: list[dict]           = []
    legs_to_skip:         set[int]             = set()

    if out_atti.exists() and not args.force and not args.dry_run:
        existing_ddl_df = pd.read_parquet(out_atti)
        legs_to_skip    = set(int(x) for x in existing_ddl_df["legislatura"].unique())
        legs_missing    = [leg for leg in args.legs if leg not in legs_to_skip]
        legs_present    = sorted(leg for leg in args.legs if leg in legs_to_skip)

        if not legs_missing:
            print(f"All requested legs already in {out_atti}. Use --force to overwrite.")
            return 0

        print(f"Skipping Leg{legs_present} (already in output). Fetching: {legs_missing}")
        args.legs = legs_missing

        if out_firm.exists():
            existing_firm_df = pd.read_parquet(out_firm)
        if out_log.exists():
            with open(out_log, encoding="utf-8") as _f:
                existing_log_entries = json.load(_f).get("results", [])

    print("fetch_metadati_senato_v2.py")
    print(f"Endpoint     : {SPARQL_ENDPOINT}")
    print(f"Legislature  : {args.legs}")
    print(f"Dry-run      : {args.dry_run}")
    print(f"Firmatari    : {not args.no_firmatari}")
    print(f"Emendamenti  : {not args.no_emend}")
    print("=" * 60)

    fetch_ts    = datetime.now(timezone.utc).isoformat()
    log: list[dict] = []
    all_ddl:  list[pd.DataFrame] = []
    all_firm: list[pd.DataFrame] = []

    for leg in args.legs:
        print(f"\n── Leg{leg} ──────────────────────────────────────")
        t0 = time.time()

        # Step 1: DDL metadata
        df_ddl = fetch_ddl(leg, dry_run=args.dry_run)
        if df_ddl.empty:
            log.append({"legislatura": leg, "status": "empty", "n_ddl": 0})
            continue

        # Step 2: Amendment counts (optional)
        if not args.no_emend:
            time.sleep(SLEEP_BETWEEN)
            df_emend = fetch_emend_counts(leg, dry_run=args.dry_run)
        else:
            df_emend = pd.DataFrame(columns=["id_fase", "n_emendamenti", "n_emendamenti_akn"])

        if not df_emend.empty:
            df_ddl = df_ddl.merge(df_emend, on="id_fase", how="left")
        else:
            df_ddl["n_emendamenti"]     = 0
            df_ddl["n_emendamenti_akn"] = 0

        df_ddl["n_emendamenti"]     = df_ddl["n_emendamenti"].fillna(0).astype(int)
        df_ddl["n_emendamenti_akn"] = df_ddl["n_emendamenti_akn"].fillna(0).astype(int)
        df_ddl["has_emendamenti"]     = df_ddl["n_emendamenti"] > 0
        df_ddl["has_emendamenti_akn"] = df_ddl["n_emendamenti_akn"] > 0

        # Steps 3–6: Signatories and group enrichment (optional)
        if not args.no_firmatari and not args.dry_run:
            time.sleep(SLEEP_BETWEEN)
            df_firm = fetch_firmatari(leg, dry_run=False)

            if not df_firm.empty:
                uris = [u for u in df_firm["uri_senatore"].dropna().unique().tolist()]

                # Step 4: Resolve foaf names for senators that have a URI link
                if uris:
                    print(f"  [NOM] Leg{leg} — senator names ({len(uris)} URIs)")
                    nomi_dict = fetch_nomi_senatori(uris)

                    def make_nome(row: pd.Series) -> str | None:
                        uri = row["uri_senatore"]
                        if uri and uri in nomi_dict:
                            n, c = nomi_dict[uri]
                            parts = [p for p in [n, c] if p]
                            if parts:
                                return " ".join(parts)
                        # Fall back to osr:presentatore already stored in nome_senatore
                        return row["nome_senatore"]

                    df_firm["nome_senatore"] = df_firm.apply(make_nome, axis=1)

                # Step 5: Parliamentary group memberships
                time.sleep(SLEEP_BETWEEN)
                df_gruppi = fetch_gruppi(leg)

                if not df_gruppi.empty:
                    # A senator may hold multiple memberships within one legislature
                    # (party change). Pick the latest membership start as primary.
                    df_gruppi_primary = (
                        df_gruppi
                        .sort_values("adGInizio", ascending=False)
                        .drop_duplicates(subset=["uri_senatore"])
                        [["uri_senatore", "gruppo_uri", "gruppo_nome",
                          "gruppo_sigla", "carica_gruppo"]]
                    )
                    df_firm = df_firm.merge(df_gruppi_primary, on="uri_senatore", how="left")
                else:
                    for col in ["gruppo_uri", "gruppo_nome", "gruppo_sigla", "carica_gruppo"]:
                        df_firm[col] = None

                # Step 6a: Enrich df_ddl with first-signatory columns
                df_primo = df_firm[df_firm["is_primo_firmatario"]].copy()
                df_primo = df_primo.rename(columns={
                    "uri_senatore":  "uri_primo_firmatario",
                    "nome_senatore": "nome_primo_firmatario",
                    "gruppo_uri":    "gruppo_primo_firmatario_uri",
                    "gruppo_nome":   "gruppo_primo_firmatario_nome",
                    "gruppo_sigla":  "gruppo_primo_firmatario_sigla",
                })
                # Guard against duplicate primo firmatario rows from data quality issues
                df_primo = df_primo.groupby("id_fase", as_index=False).first()
                primo_cols = [
                    "id_fase", "tipo_iniziativa",
                    "uri_primo_firmatario", "nome_primo_firmatario",
                    "gruppo_primo_firmatario_uri", "gruppo_primo_firmatario_nome",
                    "gruppo_primo_firmatario_sigla",
                ]
                df_primo = df_primo[[c for c in primo_cols if c in df_primo.columns]]
                df_ddl = df_ddl.merge(df_primo, on="id_fase", how="left")

                # Step 6b: Co-signatory counts
                cofirm = df_firm[~df_firm["is_primo_firmatario"]]
                n_co_uri = (
                    cofirm[cofirm["uri_senatore"].notna()]
                    .groupby("id_fase").size()
                    .rename("n_cofirmatari")
                )
                n_co_tot = cofirm.groupby("id_fase").size().rename("n_cofirmatari_totale")
                df_ddl = df_ddl.merge(n_co_uri, on="id_fase", how="left")
                df_ddl = df_ddl.merge(n_co_tot, on="id_fase", how="left")
                df_ddl["n_cofirmatari"]        = df_ddl["n_cofirmatari"].fillna(0).astype(int)
                df_ddl["n_cofirmatari_totale"] = df_ddl["n_cofirmatari_totale"].fillna(0).astype(int)

                all_firm.append(df_firm)
            else:
                _add_empty_firmatari_cols(df_ddl)
        else:
            _add_empty_firmatari_cols(df_ddl)

        # Provenance
        df_ddl["fonte"]      = "sparql:dati.senato.it"
        df_ddl["data_fetch"] = fetch_ts

        elapsed = time.time() - t0
        _print_summary(df_ddl, leg, elapsed)
        log.append(_make_log_entry(df_ddl, leg, elapsed, fetch_ts))
        all_ddl.append(df_ddl)
        time.sleep(SLEEP_BETWEEN)

    if args.dry_run or not all_ddl:
        print("\n(dry-run or no data — no files written)")
        return 0

    # Prepend data from prior runs (per-leg incremental mode).
    if existing_ddl_df is not None:
        all_ddl.insert(0, existing_ddl_df[existing_ddl_df["legislatura"].isin(legs_to_skip)])
    if existing_firm_df is not None:
        all_firm.insert(0, existing_firm_df[existing_firm_df["legislatura"].isin(legs_to_skip)])
    log = existing_log_entries + log

    # ── Write output ────────────────────────────────────────────────────────
    df_all = _reorder_atti_cols(pd.concat(all_ddl, ignore_index=True))

    if HAS_PARQUET:
        write_parquet(df_all, out_atti)
        print(f"\nSaved: {out_atti}  ({len(df_all)} rows)")
    else:
        out_csv = out_atti.with_suffix(".csv")
        df_all.to_csv(out_csv, index=False)
        print(f"\nSaved (CSV, duckdb unavailable): {out_csv}  ({len(df_all)} rows)")

    if all_firm:
        df_firm_all = _reorder_firmatari_cols(pd.concat(all_firm, ignore_index=True))
        if HAS_PARQUET:
            write_parquet(df_firm_all, out_firm)
            print(f"Saved: {out_firm}  ({len(df_firm_all)} rows)")
        else:
            df_firm_all.to_csv(out_firm.with_suffix(".csv"), index=False)

    df_cov = build_coverage(df_all)
    if not df_cov.empty:
        if HAS_PARQUET:
            write_parquet(df_cov, out_cov)
            print(f"Saved: {out_cov}")
        else:
            df_cov.to_csv(out_cov.with_suffix(".csv"), index=False)
        print("\n  Coverage per legislatura e ramo:")
        print(df_cov.to_string(index=False))

    with open(out_log, "w", encoding="utf-8") as f:
        json.dump({"run_ts": fetch_ts, "legs": args.legs, "results": log},
                  f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_log}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
