#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "duckdb"]
# ///
"""
fetch_metadati_camera_v2.py — Extends fetch_metadati_camera.py with:
                               - All signatories (primo_firmatario + altro_firmatario)
                               - Parliamentary group per signatory
                               - Full statoIter history with dates

For each legislature (Leg13–Leg19):
  - Base metadata (Queries A/B/C/D) — unchanged from v1
  - All signatories with names (Query E, cursor-range)
  - Parliamentary group per signatory (Query F, batched VALUES on deputato URIs)
  - Full statoIter history with dates (Query G, cursor-range)
  - Writes atti_camera_v2.parquet, cofirmatari_camera.parquet,
    coverage_camera_v2.parquet, fetch_log_camera_v2.json

SPARQL endpoint: https://dati.camera.it/sparql
Prefixes: ocd: <http://dati.camera.it/ocd/>, osr: <http://dati.senato.it/osr/>

Camera triplestore quirks (all confirmed 2026-05-28):
  - Every triple is duplicated: SELECT DISTINCT mandatory everywhere.
  - VALUES blocks on atti URIs cause HTTP 400 on specific subgraphs (Leg16 p.6,10):
    use FILTER cursor-range instead for all paginated queries.
  - VALUES blocks on deputato URIs (Query F) are safe: different subgraph.
  - Keyset must use STR(?atto), not xsd:integer(dc:identifier): Leg13 has ~14.5%
    non-integer IDs (navette: "105-B", "1061-bis").

Usage:
  uv run script_prova/fetch_metadati_camera_v2.py --legs 17
  uv run script_prova/fetch_metadati_camera_v2.py --force
  uv run script_prova/fetch_metadati_camera_v2.py --no-firmatari
  uv run script_prova/fetch_metadati_camera_v2.py --dry-run
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

def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write DataFrame to Parquet via DuckDB COPY TO.

    DuckDB COPY TO writes Parquet format 1.0, readable by all pyarrow versions.
    pandas.to_parquet() with pyarrow >= 23 silently defaults to format 2.6,
    which is incompatible with pyarrow < 24 (confirmed 2026-05-27).
    """
    con = _duckdb.connect()
    con.register("_df", df)
    con.execute(f"COPY _df TO '{path}' (FORMAT PARQUET)")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SPARQL_ENDPOINT = "https://dati.camera.it/sparql"
OCD             = "http://dati.camera.it/ocd/"
ALL_LEGS        = list(range(13, 20))   # 13..19

# PAGE_SIZE: atti per keyset page. ResultSetMaxRows cap ~10,000 confirmed (2026-05-28).
PAGE_SIZE   = 500
# GROUP_BATCH: max deputato URIs per QUERY_F VALUES block.
GROUP_BATCH = 50

MAX_RETRY     = 3
RETRY_WAIT    = 5
SLEEP_BETWEEN = 1.0
DATA_DIR      = Path("data")
META_DIR      = DATA_DIR / "meta"

SPARQL_HEADERS = {
    "Accept":       "application/sparql-results+json",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent":   "iter-legis-dataset/1.0 (tesi)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def leg_uri(n: int) -> str:
    """Return the Camera legislature URI for legislature n.

    Format confirmed empirically (2026-05-28): legislatura.rdf/repubblica_{N}.
    The alternative 'legislatura/{N}' (without .rdf/) returns 0 results.
    """
    return f"{OCD}legislatura.rdf/repubblica_{n}"


def parse_date(raw: str | None) -> str | None:
    """Convert Camera date string YYYYMMDD to ISO 8601 (YYYY-MM-DD)."""
    if not raw:
        return None
    s = str(raw).strip()
    if len(s) < 8:
        return None
    try:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    except Exception:
        return None


def sparql_camera(query: str, timeout: int = 60) -> list[dict] | None:
    """Execute a SPARQL query on the Camera endpoint via HTTP POST.

    Returns list[dict] on success (may be empty), None if all retries fail.
    """
    payload = urllib.parse.urlencode({
        "query":  query,
        "format": "application/sparql-results+json",
    }).encode("utf-8")
    req = urllib.request.Request(SPARQL_ENDPOINT, data=payload, headers=SPARQL_HEADERS)

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
    return None


def val(binding: dict, key: str) -> str | None:
    """Extract the string value from a SPARQL binding dict, or None if absent."""
    entry = binding.get(key)
    return entry["value"] if entry else None


# ---------------------------------------------------------------------------
# SPARQL query templates — v1 (unchanged from fetch_metadati_camera.py)
# ---------------------------------------------------------------------------

# Query A — Base metadata with URI-based keyset pagination.
# Keyset on STR(?atto): avoids ResultSetMaxRows cap and handles non-integer
# dc:identifier values ("105-B", "1061-bis"). Confirmed (2026-05-28).
# dcterms:isReferencedBy (purl.org/dc/terms/) is the correct predicate for
# the act-specific camera.it scheda URL; dc:isReferencedBy returns 0 results.
QUERY_A = """\
PREFIX ocd:     <http://dati.camera.it/ocd/>
PREFIX dc:      <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT DISTINCT ?atto ?id ?titolo ?dc_date ?tipo ?iniziativa ?url_scheda
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_uri}> ;
        dc:identifier ?id .
  FILTER(STR(?atto) > "{last_atto}")
  OPTIONAL {{ ?atto dc:title                ?titolo     }}
  OPTIONAL {{ ?atto dc:date                 ?dc_date    }}
  OPTIONAL {{ ?atto dc:type                 ?tipo       }}
  OPTIONAL {{ ?atto ocd:iniziativa          ?iniziativa }}
  OPTIONAL {{ ?atto dcterms:isReferencedBy  ?url_scheda }}
}}
ORDER BY STR(?atto)
LIMIT {page_size}
"""

# Query B — Natura label, cursor-range.
# FILTER cursor-range replaces VALUES block: VALUES causes HTTP 400 on specific
# atti subgraphs in Virtuoso Camera (confirmed 2026-05-28, Leg16 pages 6+10).
QUERY_B = """\
PREFIX ocd:  <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?atto ?natura_uri ?natura_label
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_uri}> ;
        ocd:rif_natura ?natura_uri .
  FILTER(STR(?atto) > "{cursor_start}" && STR(?atto) <= "{cursor_end}")
  OPTIONAL {{ ?natura_uri rdfs:label ?natura_label }}
}}
"""

# Query C — Last stato iter per atto (MAX dc:date via DESC sort, first-row keep).
# Coverage: ~100% Leg17-19, ~0% Leg13-16 (confirmed 2026-05-28).
QUERY_C = """\
PREFIX ocd:  <http://dati.camera.it/ocd/>
PREFIX dc:   <http://purl.org/dc/elements/1.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?atto ?si_label ?si_date
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_uri}> ;
        ocd:rif_statoIter ?si .
  ?si dc:date ?si_date .
  FILTER(STR(?atto) > "{cursor_start}" && STR(?atto) <= "{cursor_end}")
  OPTIONAL {{ ?si rdfs:label ?si_label }}
}}
ORDER BY ?atto DESC(?si_date)
"""

# Query D — Original presented text URL (MIN vta dc:date via ASC sort, first-row keep).
# Pipeline: ocd:atto → ocd:rif_versioneTestoAtto (MIN dc:date) → dcterms:isReferencedBy.
# dc:relation on ocd:atto aggregates all abbinati PDFs, NOT the act-specific URL.
QUERY_D = """\
PREFIX ocd:     <http://dati.camera.it/ocd/>
PREFIX dc:      <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT DISTINCT ?atto ?vta_date ?vta_url
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_uri}> ;
        ocd:rif_versioneTestoAtto ?vta .
  ?vta dc:date ?vta_date .
  FILTER(STR(?atto) > "{cursor_start}" && STR(?atto) <= "{cursor_end}")
  OPTIONAL {{ ?vta dcterms:isReferencedBy ?vta_url }}
}}
ORDER BY ?atto ?vta_date
"""


# ---------------------------------------------------------------------------
# SPARQL query templates — v2 (new)
# ---------------------------------------------------------------------------

# Query E — All signatories (primo_firmatario + altro_firmatario), cursor-range.
# ocd:primo_firmatario: domain ocd:atto|ocd:DOC|ocd:aic, range ocd:deputato|ocd:membroGoverno.
# ocd:altro_firmatario: domain ocd:atto|ocd:aic,          range ocd:deputato|ocd:membroGoverno.
# Both confirmed from Camera OWL ontology (ocd namespace, version 1.2).
# UNION + BIND: SPARQL 1.1, supported by Virtuoso 7+.
# SELECT DISTINCT: mandatory; Camera triplestore duplicates every triple.
# FILTER cursor-range: avoids HTTP 400 from VALUES on atti subgraphs (2026-05-28, Leg16).
QUERY_E = """\
PREFIX ocd:  <http://dati.camera.it/ocd/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT DISTINCT ?atto ?dep ?nome ?cognome ?ruolo
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_uri}> .
  FILTER(STR(?atto) > "{cursor_start}" && STR(?atto) <= "{cursor_end}")
  {{
    ?atto ocd:primo_firmatario ?dep .
    BIND("primo" AS ?ruolo)
  }} UNION {{
    ?atto ocd:altro_firmatario ?dep .
    BIND("altro" AS ?ruolo)
  }}
  OPTIONAL {{ ?dep foaf:firstName ?nome    }}
  OPTIONAL {{ ?dep foaf:surname   ?cognome }}
}}
"""

# Query F — Parliamentary group per deputy URI, batched VALUES.
# ocd:aderisce: domain ocd:deputato, range ocd:adesioneGruppo (Camera OWL ontology).
# Camera uses its own ocd: predicates for group structure (NOT osr: as in Senato).
# Confirmed empirically (2026-05-29):
#   adesioneGruppo blank node has: ocd:rif_gruppoParlamentare, ocd:startDate, rdfs:label
#   gruppoParlamentare has: ocd:rif_leg (legislature filter), dcterms:alternative (sigla)
# rdfs:label on the adesioneGruppo blank node contains the human-readable group name
# with period, e.g. "PARTITO DEMOCRATICO (19.03.2013-22.03.2018)".
# VALUES on deputato URIs is safe: HTTP 400 affects atti subgraphs only (2026-05-28).
# Max GROUP_BATCH=50 URIs per call to stay within Virtuoso query complexity limits.
QUERY_F = """\
PREFIX ocd:     <http://dati.camera.it/ocd/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?dep ?gruppoURI ?gruppo_nome ?gruppo_sigla ?adG_start
WHERE {{
  VALUES ?dep {{ {dep_uris} }}
  ?dep ocd:aderisce ?adG .
  ?adG ocd:rif_gruppoParlamentare ?gruppoURI ;
       ocd:startDate ?adG_start .
  ?gruppoURI ocd:rif_leg <{leg_uri}> .
  OPTIONAL {{ ?adG       rdfs:label           ?gruppo_nome  . }}
  OPTIONAL {{ ?gruppoURI dcterms:alternative   ?gruppo_sigla . }}
}}
"""

# Query G — Full statoIter history per atto, cursor-range.
# ocd:rif_statoIter is multi-valued (avg ~6.4 unique states per atto in Leg17).
# Returns every (atto, stato, label, date) triple. Python extracts:
#   data_prima_assegnazione = MIN(date) WHERE label = "Da assegnare"
#   data_approvazione       = MIN(date) WHERE label = "Approvato definitivamente. Legge"
# Coverage: ~100% Leg17-19, ~0% Leg13-16 (pre-digital). Confirmed (2026-05-28).
QUERY_G = """\
PREFIX ocd:  <http://dati.camera.it/ocd/>
PREFIX dc:   <http://purl.org/dc/elements/1.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?atto ?stato ?si_label ?si_date
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_uri}> ;
        ocd:rif_statoIter ?stato .
  ?stato dc:date ?si_date .
  FILTER(STR(?atto) > "{cursor_start}" && STR(?atto) <= "{cursor_end}")
  OPTIONAL {{ ?stato rdfs:label ?si_label }}
}}
ORDER BY ?atto ?si_date
"""


# ---------------------------------------------------------------------------
# v1 cursor-range fetchers (Queries B, C, D — unchanged)
# ---------------------------------------------------------------------------

def _fetch_natura(luri: str, cs: str, ce: str) -> dict[str, str | None]:
    """Fetch natura label for all atti in the cursor range (Query B)."""
    rows = sparql_camera(QUERY_B.format(leg_uri=luri, cursor_start=cs, cursor_end=ce))
    result: dict[str, str | None] = {}
    if not rows:
        return result
    for r in rows:
        a = val(r, "atto")
        if not a or a in result:
            continue
        label = val(r, "natura_label")
        if not label:
            nat_uri = val(r, "natura_uri") or ""
            label = nat_uri.rstrip("/").split("/")[-1] or None
        result[a] = label
    return result


def _fetch_stato(luri: str, cs: str, ce: str) -> dict[str, tuple[str | None, str | None]]:
    """Fetch last stato iter per atto in cursor range (Query C, DESC sort → first-row = MAX)."""
    rows = sparql_camera(QUERY_C.format(leg_uri=luri, cursor_start=cs, cursor_end=ce))
    result: dict[str, tuple[str | None, str | None]] = {}
    if not rows:
        return result
    for r in rows:
        a = val(r, "atto")
        if not a or a in result:
            continue
        result[a] = (val(r, "si_label"), val(r, "si_date"))
    return result


def _fetch_vta(luri: str, cs: str, ce: str) -> dict[str, tuple[str | None, str | None]]:
    """Fetch original text URL per atto in cursor range (Query D, ASC sort → first-row = MIN)."""
    rows = sparql_camera(QUERY_D.format(leg_uri=luri, cursor_start=cs, cursor_end=ce))
    result: dict[str, tuple[str | None, str | None]] = {}
    if not rows:
        return result
    for r in rows:
        a = val(r, "atto")
        if not a or a in result:
            continue
        result[a] = (val(r, "vta_date"), val(r, "vta_url"))
    return result


# ---------------------------------------------------------------------------
# Per-legislature keyset driver
# ---------------------------------------------------------------------------

def _iter_pages(luri: str) -> list[tuple[str, str]]:
    """Return list of (cursor_start, cursor_end) pairs covering all atti for luri.

    Runs Query A (id-only semantics: extra columns discarded) to advance the
    keyset cursor page by page. Each pair defines a FILTER cursor-range suitable
    for Queries B/C/D/E/G.
    """
    pages: list[tuple[str, str]] = []
    last_atto = ""
    while True:
        rows = sparql_camera(QUERY_A.format(leg_uri=luri, last_atto=last_atto, page_size=PAGE_SIZE))
        if not rows:
            break
        page_attos = [val(r, "atto") for r in rows if val(r, "atto")]
        if not page_attos:
            break
        prev = last_atto
        last_atto = max(page_attos)
        pages.append((prev, last_atto))
        if len(rows) < PAGE_SIZE:
            break
        time.sleep(SLEEP_BETWEEN)
    return pages


# ---------------------------------------------------------------------------
# Public fetch functions
# ---------------------------------------------------------------------------

def fetch_atti(
    leg: int,
    dry_run: bool = False,
    no_testo: bool = False,
    fetch_ts: str = "",
) -> pd.DataFrame:
    """Fetch all atti for one legislature with base structured metadata.

    Identical logic to fetch_metadati_camera.py. Keyset pages via Query A;
    cursor-range sub-queries B/C/D per page.
    """
    luri = leg_uri(leg)
    print(f"  [A/B/C/D] Leg{leg} — fetch_atti  page_size={PAGE_SIZE}")

    if dry_run:
        print(f"\n  === QUERY A (dry-run, LIMIT 5) ===")
        print(QUERY_A.format(leg_uri=luri, last_atto="", page_size=5))
        print("=" * 60)
        return pd.DataFrame()

    all_records: list[dict] = []
    last_atto = ""
    page      = 0

    while True:
        page += 1
        prev_cursor = last_atto

        rows_a = sparql_camera(QUERY_A.format(leg_uri=luri, last_atto=last_atto, page_size=PAGE_SIZE))
        if not rows_a:
            break

        page_attos = [val(r, "atto") for r in rows_a if val(r, "atto")]
        last_atto  = max(page_attos) if page_attos else last_atto

        time.sleep(SLEEP_BETWEEN)
        natura_map = _fetch_natura(luri, prev_cursor, last_atto)

        time.sleep(SLEEP_BETWEEN)
        stato_map = _fetch_stato(luri, prev_cursor, last_atto)

        vta_map: dict[str, tuple[str | None, str | None]] = {}
        if not no_testo:
            time.sleep(SLEEP_BETWEEN)
            vta_map = _fetch_vta(luri, prev_cursor, last_atto)

        seen: set[str] = set()
        for r in rows_a:
            atto_uri = val(r, "atto")
            if not atto_uri or atto_uri in seen:
                continue
            seen.add(atto_uri)

            id_atto = atto_uri.rstrip("/").split("/")[-1]
            id_raw  = val(r, "id") or ""
            try:
                id_num = int(id_raw.strip())
            except ValueError:
                id_num = None

            dc_date = val(r, "dc_date")

            natura = natura_map.get(atto_uri)

            stato_tup      = stato_map.get(atto_uri)
            stato_iter     = stato_tup[0] if stato_tup else None
            data_stato_raw = stato_tup[1] if stato_tup else None

            vta_tup  = vta_map.get(atto_uri)
            vta_date = vta_tup[0] if vta_tup else None
            vta_url  = vta_tup[1] if vta_tup else None

            # Prefer MIN(vta.dc:date) (~99% for Leg17-19); fall back to dc:date on
            # the atto for Leg13-16 where versioneTestoAtto coverage is near zero.
            data_pres_raw = vta_date if vta_date else dc_date

            all_records.append({
                "id_atto":              id_atto,
                "id_numerico":          id_num,
                "legislatura":          leg,
                "titolo":               val(r, "titolo"),
                "data_presentazione":   parse_date(data_pres_raw),
                "tipo_atto":            val(r, "tipo"),
                "natura":               natura,
                "iniziativa":           val(r, "iniziativa"),
                "stato_iter":           stato_iter,
                "data_stato_iter":      parse_date(data_stato_raw),
                "url_testo_presentato": vta_url,
                "has_testo":            vta_url is not None,
                "url_scheda_camera":    val(r, "url_scheda"),
                "fonte":                "sparql:dati.camera.it",
                "data_fetch":           fetch_ts,
            })

        print(f"      page={page:>3}  cursor={last_atto.split('/')[-1]:<16}  +{len(seen):>3}  total={len(all_records)}")

        if len(rows_a) < PAGE_SIZE:
            break
        time.sleep(SLEEP_BETWEEN)

    if not all_records:
        print(f"  ⚠️  No atti found for Leg{leg}.")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    before = len(df)
    df = df.drop_duplicates(subset=["id_atto"])
    if len(df) < before:
        print(f"  ℹ️  Deduplicated {before - len(df)} extra id_atto rows.")
    return df


def fetch_firmatari(leg: int, fetch_ts: str = "") -> pd.DataFrame:
    """Fetch all signatories for one legislature (Query E).

    Runs an independent keyset pass (cursor pages from Query A), then for each
    page queries both ocd:primo_firmatario and ocd:altro_firmatario via UNION.
    FILTER cursor-range avoids HTTP 400 from VALUES on atti (confirmed 2026-05-28).
    SELECT DISTINCT handles Camera triple duplication.

    If the same (atto, dep) pair appears as both primo and altro, the primo role
    is retained (sort by is_primo_firmatario DESC before dedup).

    Returns a tall DataFrame: one row per (atto, deputato) pair.
    """
    luri = leg_uri(leg)
    print(f"  [E] Leg{leg} — fetch_firmatari  cursor-range per page")

    pages = _iter_pages(luri)
    if not pages:
        print(f"  ⚠️  No pages for Leg{leg}.")
        return pd.DataFrame()

    all_records: list[dict] = []

    for page_idx, (cs, ce) in enumerate(pages, 1):
        time.sleep(SLEEP_BETWEEN)
        rows_e = sparql_camera(QUERY_E.format(leg_uri=luri, cursor_start=cs, cursor_end=ce))

        n_page = 0
        if rows_e:
            for r in rows_e:
                atto_uri = val(r, "atto")
                dep_uri  = val(r, "dep")
                if not atto_uri or not dep_uri:
                    continue

                ruolo   = val(r, "ruolo") or "altro"
                nome    = val(r, "nome")
                cognome = val(r, "cognome")
                nome_leggibile: str | None = None
                if nome or cognome:
                    nome_leggibile = " ".join(p for p in [nome, cognome] if p)

                all_records.append({
                    "id_atto":             atto_uri.rstrip("/").split("/")[-1],
                    "atto_uri":            atto_uri,
                    "legislatura":         leg,
                    "uri_deputato":        dep_uri,
                    "nome_deputato":       nome_leggibile,
                    "is_primo_firmatario": ruolo == "primo",
                    "data_fetch":          fetch_ts,
                })
                n_page += 1

        print(f"      page={page_idx:>3}  cursor={ce.split('/')[-1]:<16}  firmatari_rows={n_page}")

    if not all_records:
        print(f"  ⚠️  No firmatari found for Leg{leg}.")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    # If same (atto, dep) appears in both primo and altro, keep primo.
    df = (
        df.sort_values("is_primo_firmatario", ascending=False)
          .drop_duplicates(subset=["id_atto", "uri_deputato"])
          .reset_index(drop=True)
    )
    return df


def fetch_gruppi(dep_uris: list[str], leg: int) -> pd.DataFrame:
    """Fetch parliamentary group for each deputy URI via batched VALUES (Query F).

    Camera group structure (confirmed 2026-05-29):
      ocd:aderisce → adesioneGruppo blank node → ocd:rif_gruppoParlamentare → gruppoURI
    Group name: rdfs:label on the adesioneGruppo blank node (includes period range).
    Group sigla: dcterms:alternative on the gruppoParlamentare URI.
    Legislature filter: ocd:rif_leg on the gruppoParlamentare URI.

    VALUES blocks on deputato URIs are safe: HTTP 400 only affects atti subgraph
    VALUES queries (confirmed 2026-05-28, Leg16). Batches capped at GROUP_BATCH=50.

    When a deputy changed groups within the legislature, keeps the most recent
    membership (MAX adG_start) to represent their primary affiliation.

    Returns one row per unique deputy URI.
    """
    if not dep_uris:
        return pd.DataFrame()

    luri = leg_uri(leg)
    # Filter to proper deputato URIs only (blank nodes from membroGoverno have no group data).
    unique_uris = list(dict.fromkeys(
        u for u in dep_uris if u and not u.startswith("nodeID://")
    ))
    if not unique_uris:
        return pd.DataFrame()

    print(f"  [F] fetch_gruppi  {len(unique_uris)} unique deputies  batch={GROUP_BATCH}")

    all_rows: list[dict] = []
    chunks = [unique_uris[i:i + GROUP_BATCH] for i in range(0, len(unique_uris), GROUP_BATCH)]

    for chunk_idx, chunk in enumerate(chunks):
        dep_uris_str = " ".join(f"<{u}>" for u in chunk)
        rows = sparql_camera(
            QUERY_F.format(dep_uris=dep_uris_str, leg_uri=luri),
            timeout=90,
        )
        if rows:
            for r in rows:
                dep = val(r, "dep")
                if not dep:
                    continue
                all_rows.append({
                    "uri_deputato": dep,
                    "gruppo_uri":   val(r, "gruppoURI"),
                    "gruppo_nome":  val(r, "gruppo_nome"),
                    "gruppo_sigla": val(r, "gruppo_sigla"),
                    "_adG_start":   val(r, "adG_start"),
                })
        if chunk_idx < len(chunks) - 1:
            time.sleep(SLEEP_BETWEEN)

    if not all_rows:
        print("  ⚠️  No group data returned.")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    # Keep most recent group membership per deputy (handles mid-legislature group changes).
    df = (
        df.sort_values("_adG_start", ascending=False, na_position="last")
          .drop_duplicates(subset=["uri_deputato"])
          .drop(columns=["_adG_start"])
          .reset_index(drop=True)
    )
    print(f"      {len(df)} deputies with group data")
    return df


def fetch_stati_iter(leg: int, fetch_ts: str = "") -> pd.DataFrame:
    """Fetch the complete statoIter history for one legislature (Query G).

    Independent keyset pass (cursor pages from Query A). Returns a tall DataFrame
    (one row per atto × stato). Coverage: ~100% Leg17-19, ~0% Leg13-16.

    Label constants used downstream:
      "Da assegnare"                     → data_prima_assegnazione
      "Approvato definitivamente. Legge" → data_approvazione
    """
    luri = leg_uri(leg)
    print(f"  [G] Leg{leg} — fetch_stati_iter  cursor-range per page")

    pages = _iter_pages(luri)
    if not pages:
        print(f"  ⚠️  No pages for Leg{leg}.")
        return pd.DataFrame()

    all_records: list[dict] = []

    for page_idx, (cs, ce) in enumerate(pages, 1):
        time.sleep(SLEEP_BETWEEN)
        rows_g = sparql_camera(QUERY_G.format(leg_uri=luri, cursor_start=cs, cursor_end=ce))

        n_page = 0
        if rows_g:
            seen_pairs: set[tuple[str, str]] = set()
            for r in rows_g:
                atto_uri = val(r, "atto")
                stato    = val(r, "stato")
                if not atto_uri or not stato:
                    continue
                # SELECT DISTINCT handles Camera duplication; this is a safety net.
                pair = (atto_uri, stato)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                all_records.append({
                    "id_atto":    atto_uri.rstrip("/").split("/")[-1],
                    "atto_uri":   atto_uri,
                    "legislatura": leg,
                    "stato_uri":  stato,
                    "si_label":   val(r, "si_label"),
                    "si_date":    parse_date(val(r, "si_date")),
                    "data_fetch": fetch_ts,
                })
                n_page += 1

        print(f"      page={page_idx:>3}  cursor={ce.split('/')[-1]:<16}  stati_rows={n_page}")

    if not all_records:
        print(f"  ⚠️  No statoIter history for Leg{leg}.")
        return pd.DataFrame()

    return pd.DataFrame(all_records)


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

def _summarise_firmatari(df_firm: pd.DataFrame) -> pd.DataFrame:
    """Extract per-atto summary from the firmatari tall table.

    Returns columns: id_atto, primo_firmatario_uri, primo_firmatario_nome, n_cofirmatari.
    """
    if df_firm.empty:
        return pd.DataFrame(columns=[
            "id_atto", "primo_firmatario_uri", "primo_firmatario_nome", "n_cofirmatari"
        ])

    df_primo = (
        df_firm[df_firm["is_primo_firmatario"]]
        .drop_duplicates("id_atto")[["id_atto", "uri_deputato", "nome_deputato"]]
        .rename(columns={"uri_deputato":  "primo_firmatario_uri",
                         "nome_deputato": "primo_firmatario_nome"})
    )

    df_n_co = (
        df_firm[~df_firm["is_primo_firmatario"]]
        .groupby("id_atto", as_index=False)["uri_deputato"]
        .nunique()
        .rename(columns={"uri_deputato": "n_cofirmatari"})
    )

    summary = df_primo.merge(df_n_co, on="id_atto", how="outer")
    summary["n_cofirmatari"] = summary["n_cofirmatari"].fillna(0).astype(int)
    return summary


def _summarise_stati(df_stati: pd.DataFrame) -> pd.DataFrame:
    """Extract data_prima_assegnazione and data_approvazione from the full history.

    Returns columns: id_atto, data_prima_assegnazione, data_approvazione.
    """
    if df_stati.empty:
        return pd.DataFrame(columns=["id_atto", "data_prima_assegnazione", "data_approvazione"])

    LABEL_ASS = "Da assegnare"
    LABEL_APP = "Approvato definitivamente. Legge"

    df_ass = (
        df_stati[df_stati["si_label"] == LABEL_ASS]
        .groupby("id_atto", as_index=False)["si_date"]
        .min()
        .rename(columns={"si_date": "data_prima_assegnazione"})
    )

    df_app = (
        df_stati[df_stati["si_label"] == LABEL_APP]
        .groupby("id_atto", as_index=False)["si_date"]
        .min()
        .rename(columns={"si_date": "data_approvazione"})
    )

    return df_ass.merge(df_app, on="id_atto", how="outer")


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def build_coverage(df: pd.DataFrame, fetch_ts: str) -> pd.DataFrame:
    """Compute per-legislature coverage statistics for the v2 schema."""
    if df.empty:
        return pd.DataFrame()

    def _notna_sum(col: str):
        return lambda x: x.notna().sum()

    def _pos_sum(col: str):
        return lambda x: (pd.to_numeric(x, errors="coerce").fillna(0) > 0).sum()

    grp = df.groupby("legislatura", sort=True)
    cov = grp.agg(
        n_atti                  = ("id_atto",                "count"),
        n_has_testo             = ("has_testo",              "sum"),
        n_has_natura            = ("natura",                 _notna_sum("natura")),
        n_has_stato             = ("stato_iter",             _notna_sum("stato_iter")),
        n_has_primo_firmatario  = ("primo_firmatario_uri",   _notna_sum("primo_firmatario_uri")),
        n_has_cofirmatari       = ("n_cofirmatari",          _pos_sum("n_cofirmatari")),
        n_has_data_assegnazione = ("data_prima_assegnazione", _notna_sum("data_prima_assegnazione")),
        n_has_data_approvazione = ("data_approvazione",      _notna_sum("data_approvazione")),
    ).reset_index()

    int_cols = [
        "n_atti", "n_has_testo", "n_has_natura", "n_has_stato",
        "n_has_primo_firmatario", "n_has_cofirmatari",
        "n_has_data_assegnazione", "n_has_data_approvazione",
    ]
    for col in int_cols:
        cov[col] = cov[col].astype(int)

    for n_col, pct_col in [
        ("n_has_testo",              "pct_has_testo"),
        ("n_has_natura",             "pct_has_natura"),
        ("n_has_stato",              "pct_has_stato"),
        ("n_has_primo_firmatario",   "pct_has_primo_firmatario"),
        ("n_has_data_assegnazione",  "pct_has_data_assegnazione"),
        ("n_has_data_approvazione",  "pct_has_data_approvazione"),
    ]:
        cov[pct_col] = (cov[n_col] / cov["n_atti"] * 100).round(1)

    cov["data_fetch"] = fetch_ts
    return cov


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Camera metadata v2: adds cofirmatari, groups, full statoIter history."
    )
    parser.add_argument(
        "--legs", type=int, nargs="+", default=ALL_LEGS,
        help=f"Legislature to fetch (default: all {ALL_LEGS})"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch and overwrite even if data for these legs already exists"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print SPARQL queries without executing any fetch"
    )
    parser.add_argument(
        "--no-testo", action="store_true",
        help="Skip versioneTestoAtto query (url_testo_presentato will be null)"
    )
    parser.add_argument(
        "--no-firmatari", action="store_true",
        help="Skip Queries E/F/G (v2 columns will be null)"
    )
    args = parser.parse_args()

    META_DIR.mkdir(parents=True, exist_ok=True)
    out_atti   = META_DIR / "atti_camera_v2.parquet"
    out_cofirm = META_DIR / "cofirmatari_camera.parquet"
    out_cov    = META_DIR / "coverage_camera_v2.parquet"
    out_log    = META_DIR / "fetch_log_camera_v2.json"

    fetch_ts = datetime.now(timezone.utc).isoformat()

    print("fetch_metadati_camera_v2.py")
    print(f"Endpoint     : {SPARQL_ENDPOINT}")
    print(f"Legislature  : {args.legs}")
    print(f"Dry-run      : {args.dry_run}")
    print(f"No-testo     : {args.no_testo}")
    print(f"No-firmatari : {args.no_firmatari}")
    print("=" * 60)

    # Leg-level idempotency: load existing parquet so legs not being re-fetched
    # are preserved in the final merged output.
    legs_to_fetch = list(args.legs)
    df_existing   = pd.DataFrame()

    if out_atti.exists() and not args.dry_run:
        try:
            if HAS_PARQUET:
                con = _duckdb.connect()
                df_existing = con.execute(f"SELECT * FROM '{out_atti}'").df()
                con.close()
            else:
                df_existing = pd.read_csv(out_atti.with_suffix(".csv"))
            done_legs = set(df_existing["legislatura"].astype(int).unique().tolist())
            if not args.force:
                skip = [l for l in legs_to_fetch if l in done_legs]
                legs_to_fetch = [l for l in legs_to_fetch if l not in done_legs]
                if skip:
                    print(f"ℹ️  Already present: Leg{skip}. Use --force to re-fetch.")
                if not legs_to_fetch:
                    print("✅ All requested legs already present. Nothing to do.")
                    return 0
        except Exception as e:
            print(f"⚠️  Could not read existing {out_atti}: {e}. Will overwrite.")
            df_existing = pd.DataFrame()

    log: list[dict]             = []
    all_atti_dfs:   list[pd.DataFrame] = []
    all_cofirm_dfs: list[pd.DataFrame] = []

    for leg in legs_to_fetch:
        print(f"\n── Leg{leg} ──────────────────────────────────────")
        t0 = time.time()

        # Step 1 — base atti metadata (v1 logic)
        df_atti = fetch_atti(leg, dry_run=args.dry_run, no_testo=args.no_testo, fetch_ts=fetch_ts)
        if df_atti.empty:
            log.append({"legislatura": leg, "status": "empty_atti", "n_atti": 0})
            continue

        df_firm   = pd.DataFrame()
        df_gruppi = pd.DataFrame()
        df_stati  = pd.DataFrame()

        if not args.no_firmatari and not args.dry_run:
            # Step 2 — all signatories (Query E)
            time.sleep(SLEEP_BETWEEN)
            df_firm = fetch_firmatari(leg, fetch_ts=fetch_ts)

            # Step 3 — parliamentary groups (Query F)
            if not df_firm.empty:
                time.sleep(SLEEP_BETWEEN)
                all_dep_uris = df_firm["uri_deputato"].dropna().unique().tolist()
                df_gruppi = fetch_gruppi(all_dep_uris, leg)

            # Step 4 — full statoIter history (Query G)
            time.sleep(SLEEP_BETWEEN)
            df_stati = fetch_stati_iter(leg, fetch_ts=fetch_ts)

        # Step 5 — merge summaries into df_atti
        df_firm_summary = _summarise_firmatari(df_firm)
        if not df_firm_summary.empty:
            df_atti = df_atti.merge(df_firm_summary, on="id_atto", how="left")
        else:
            df_atti["primo_firmatario_uri"]  = None
            df_atti["primo_firmatario_nome"] = None
            df_atti["n_cofirmatari"]         = pd.NA

        df_stati_summary = _summarise_stati(df_stati)
        if not df_stati_summary.empty:
            df_atti = df_atti.merge(df_stati_summary, on="id_atto", how="left")
        else:
            df_atti["data_prima_assegnazione"] = None
            df_atti["data_approvazione"]        = None

        # Build cofirmatari table: firmatari joined with group info
        if not df_firm.empty:
            df_cofirm = df_firm.copy()
            if not df_gruppi.empty:
                df_cofirm = df_cofirm.merge(df_gruppi, on="uri_deputato", how="left")
            else:
                df_cofirm["gruppo_uri"]   = None
                df_cofirm["gruppo_nome"]  = None
                df_cofirm["gruppo_sigla"] = None
            all_cofirm_dfs.append(df_cofirm.drop(columns=["atto_uri"], errors="ignore"))

        # Stats summary
        elapsed = time.time() - t0
        n       = len(df_atti)

        def _pct(col: str) -> tuple[int, str]:
            if col not in df_atti.columns:
                return 0, "n/a"
            v = int(df_atti[col].notna().sum())
            return v, f"{v/n*100:.1f}%"

        n_pf, pct_pf   = _pct("primo_firmatario_uri")
        n_co_col       = "n_cofirmatari"
        n_co           = int((df_atti[n_co_col].fillna(0) > 0).sum()) if n_co_col in df_atti.columns else 0
        n_ass, pct_ass = _pct("data_prima_assegnazione")
        n_app, pct_app = _pct("data_approvazione")

        print(f"\n  ✅ Leg{leg}: {n} atti in {elapsed:.1f}s")
        print(f"     Primo firmatario      : {n_pf}/{n} ({pct_pf})")
        print(f"     Con cofirmatari       : {n_co}/{n} ({n_co/n*100:.1f}%)")
        print(f"     data_assegnazione     : {n_ass}/{n} ({pct_ass})")
        print(f"     data_approvazione     : {n_app}/{n} ({pct_app})")

        log.append({
            "legislatura":             leg,
            "status":                  "ok",
            "n_atti":                  n,
            "n_has_primo_firmatario":  n_pf,
            "n_has_cofirmatari":       n_co,
            "n_has_data_assegnazione": n_ass,
            "n_has_data_approvazione": n_app,
            "elapsed_s":               round(elapsed, 1),
            "fetch_ts":                fetch_ts,
        })

        all_atti_dfs.append(df_atti)
        time.sleep(SLEEP_BETWEEN)

    if args.dry_run or not all_atti_dfs:
        print("\n(dry-run or no data — no files written)")
        return 0

    # Merge with existing data for legs not re-fetched
    df_new = pd.concat(all_atti_dfs, ignore_index=True)
    if not df_existing.empty:
        legs_new_set = set(df_new["legislatura"].astype(int).unique())
        df_carry     = df_existing[
            ~df_existing["legislatura"].astype(int).isin(legs_new_set)
        ].copy()
        df_all = pd.concat([df_carry, df_new], ignore_index=True)
    else:
        df_all = df_new

    # Canonical column order for atti_camera_v2.parquet
    col_order = [
        "id_atto", "id_numerico", "legislatura",
        "titolo", "data_presentazione", "tipo_atto",
        "natura", "iniziativa",
        "primo_firmatario_uri", "primo_firmatario_nome", "n_cofirmatari",
        "stato_iter", "data_stato_iter",
        "data_prima_assegnazione", "data_approvazione",
        "url_testo_presentato", "has_testo",
        "url_scheda_camera",
        "fonte", "data_fetch",
    ]
    extra = [c for c in df_all.columns if c not in col_order]
    if extra:
        print(f"\nℹ️  Extra columns: {extra}")
    df_all = df_all[[c for c in col_order if c in df_all.columns] + extra]
    df_all = df_all.sort_values(["legislatura", "id_numerico"]).reset_index(drop=True)

    # Write atti_camera_v2.parquet
    if HAS_PARQUET:
        write_parquet(df_all, out_atti)
        print(f"\n✅ Saved: {out_atti}  ({len(df_all)} rows)")
    else:
        out_csv = out_atti.with_suffix(".csv")
        df_all.to_csv(out_csv, index=False)
        print(f"\n✅ Saved (CSV, duckdb unavailable): {out_csv}  ({len(df_all)} rows)")

    # Write cofirmatari_camera.parquet
    if all_cofirm_dfs:
        df_all_cofirm = pd.concat(all_cofirm_dfs, ignore_index=True)
        cofirm_col_order = [
            "id_atto", "legislatura",
            "uri_deputato", "nome_deputato", "is_primo_firmatario",
            "gruppo_uri", "gruppo_nome", "gruppo_sigla",
            "data_fetch",
        ]
        extra_co = [c for c in df_all_cofirm.columns if c not in cofirm_col_order]
        df_all_cofirm = df_all_cofirm[
            [c for c in cofirm_col_order if c in df_all_cofirm.columns] + extra_co
        ]
        if HAS_PARQUET:
            write_parquet(df_all_cofirm, out_cofirm)
            print(f"✅ Saved: {out_cofirm}  ({len(df_all_cofirm)} rows)")
        else:
            out_co_csv = out_cofirm.with_suffix(".csv")
            df_all_cofirm.to_csv(out_co_csv, index=False)
            print(f"✅ Saved (CSV): {out_co_csv}  ({len(df_all_cofirm)} rows)")

    # Write coverage_camera_v2.parquet
    df_cov = build_coverage(df_all, fetch_ts)
    if not df_cov.empty:
        if HAS_PARQUET:
            write_parquet(df_cov, out_cov)
            print(f"✅ Saved: {out_cov}")
        else:
            out_cov_csv = out_cov.with_suffix(".csv")
            df_cov.to_csv(out_cov_csv, index=False)
            print(f"✅ Saved (CSV): {out_cov_csv}")
        print("\n  Coverage per legislatura:")
        print(df_cov.to_string(index=False))

    # Write fetch_log_camera_v2.json
    with open(out_log, "w", encoding="utf-8") as f:
        json.dump(
            {"run_ts": fetch_ts, "legs": legs_to_fetch, "results": log},
            f, ensure_ascii=False, indent=2,
        )
    print(f"✅ Log: {out_log}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
