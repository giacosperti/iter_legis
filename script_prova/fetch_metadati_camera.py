#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "duckdb"]
# ///
"""
fetch_metadati_camera.py — Estrae metadati degli atti legislativi dalla Camera.
                           Fetches Camera dei Deputati legislative act metadata via SPARQL.

Per ogni legislatura (Leg13–Leg19):
  - Recupera tutti gli atti (ocd:atto) con metadati strutturati via SPARQL
  - Per ogni pagina di 500 atti: natura (Query B), ultimo stato iter (C),
    URL testo presentato via versioneTestoAtto (D)
  - Calcola flag has_testo
  - Salva su data/meta/atti_camera.parquet
  - Salva report di copertura su data/meta/coverage_camera.parquet
  - Salva log fetch su data/meta/fetch_log_camera.json

SPARQL endpoint: https://dati.camera.it/sparql
Prefisso:        ocd: <http://dati.camera.it/ocd/>

Limitazioni note:
  - Leg13–15: rif_natura, rif_statoIter, rif_versioneTestoAtto assenti o quasi assenti
    nel triplestore. data_presentazione cade su dc:date sull'atto (100% coverage).
  - Leg16: triplestore strutturalmente incompleto — statoIter e versioneTestoAtto
    presenti solo per ~0.1% degli atti. Solo metadati base disponibili.
  - dc:relation su ocd:atto NON è l'URL del testo dell'atto (aggrega tutti gli
    abbinati in discussione congiunta). Pipeline corretta: versioneTestoAtto → dcterms:isReferencedBy.

Usage:
  uv run script_prova/fetch_metadati_camera.py
  uv run script_prova/fetch_metadati_camera.py --legs 17
  uv run script_prova/fetch_metadati_camera.py --legs 17 18 19
  uv run script_prova/fetch_metadati_camera.py --force     # re-fetches all requested legs
  uv run script_prova/fetch_metadati_camera.py --dry-run   # prints queries, no fetch
  uv run script_prova/fetch_metadati_camera.py --no-testo  # skips versioneTestoAtto query
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
    # CSV fallback when duckdb is unavailable
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

# PAGE_SIZE: atti per keyset page. The Camera Virtuoso endpoint enforces a
# ResultSetMaxRows cap (same ~10,000 as dati.senato.it): OFFSET >= 10,000
# returns an empty body. PAGE_SIZE=500 keeps each page well within the limit.
# Confirmed empirically (2026-05-28, diag_camera_atti.py section 2).
PAGE_SIZE     = 500

MAX_RETRY     = 3
RETRY_WAIT    = 5      # seconds between retries
SLEEP_BETWEEN = 1.0    # seconds between SPARQL calls
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
    'legislatura/{N}' (without the .rdf/ segment) returns 0 results.
    The triplestore also contains 'regno_{N}' URIs for pre-1948 parliaments;
    using 'repubblica_{N}' excludes them from all queries.
    """
    return f"{OCD}legislatura.rdf/repubblica_{n}"


def parse_date(raw: str | None) -> str | None:
    """Convert Camera date string YYYYMMDD to ISO 8601 (YYYY-MM-DD).

    Returns None on missing or malformed input.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if len(s) < 8:
        return None
    try:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    except Exception:
        return None


def sparql(query: str, timeout: int = 60) -> list[dict] | None:
    """Execute a SPARQL query via HTTP POST and return bindings as a list of dicts.

    Returns:
      list[dict]  — successful response (may be empty for genuinely 0-result queries).
      None        — all MAX_RETRY attempts failed (HTTP error or network error).
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
    # All retries exhausted — signal persistent failure to the caller.
    return None


def val(binding: dict, key: str) -> str | None:
    """Extract the string value from a SPARQL binding dict, or None if absent."""
    entry = binding.get(key)
    return entry["value"] if entry else None


# ---------------------------------------------------------------------------
# SPARQL query templates
# ---------------------------------------------------------------------------

# Query A — Base metadata with URI-based keyset pagination.
#
# Keyset strategy: FILTER(STR(?atto) > "{last_atto}") + ORDER BY STR(?atto).
# Each call is a fresh query for Virtuoso, bypassing the ResultSetMaxRows cap
# that blocks LIMIT/OFFSET at OFFSET >= 10,000. Confirmed (2026-05-28).
#
# URI keyset is required (not integer dc:identifier) because some atti have
# non-integer dc:identifier values (e.g. "105-B", "1061-bis" for navette and
# variants). FILTER(xsd:integer(?id) > N) silently excludes those atti.
# Confirmed empirically: Leg13 has ~1,199 non-integer atti out of 8,281 total.
# Confirmed (2026-05-28).
#
# String ordering of URIs is lexicographic (e.g. "ac13_1" < "ac13_10" < "ac13_100");
# this is a valid total order — all atti are reached regardless of id format.
#
# Triple RDF duplicate: each ocd:atto has rdf:type ocd:atto and ocd:rif_leg
# present TWICE in the graph. SELECT DISTINCT is mandatory. Confirmed (2026-05-28).
#
# dcterms:isReferencedBy (purl.org/dc/terms/) is the correct predicate for the
# act-specific camera.it scheda URL. dc:isReferencedBy (dc/elements/1.1/)
# returns 0 results. Confirmed (2026-05-28).
#
# dc:date on ocd:atto: presentation date, format YYYYMMDD, ~100% coverage.
# Used as fallback for data_presentazione when versioneTestoAtto is unavailable.
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

# Queries B / C / D use cursor-range FILTER instead of VALUES blocks.
#
# Root cause of original VALUES approach failure (confirmed 2026-05-28):
# Virtuoso Camera returns HTTP 400 for specific URI sets in VALUES blocks
# regardless of block size (batch_size=500, 100, 50 all trigger the same
# failures on Leg16 pages 6 and 10). The failure is deterministic and
# unrelated to payload size or timing — it is Virtuoso's query cost
# estimator rejecting multi-URI VALUES joins for certain atti subgraphs.
#
# Fix: use the same FILTER(STR(?atto) > cursor_start && STR(?atto) <= cursor_end)
# strategy as Query A. Each sub-query covers exactly the URI range of the
# current page. No VALUES block → no HTTP 400.

# Query B — Natura (linked entity with human-readable label), cursor-range.
#
# ocd:rif_natura links to a named entity (e.g. natura.rdf/proposta_legge_ordinaria).
# rdfs:label on that entity provides the human-readable string.
# Some entities lack rdfs:label (e.g. disegno_legge_costituzionale in Leg17);
# the Python code falls back to the URI last segment in that case.
# Coverage: ~100% for Leg16-19, ~0% for Leg13-15 (confirmed 2026-05-28).
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

# Query C — Last stato iter per atto, cursor-range (sorted DESC by dc:date).
#
# ocd:rif_statoIter is multi-valued (avg ~3.2 unique states per atto in Leg17
# after accounting for triple duplication). Results sorted DESC by dc:date;
# Python keeps the first row per atto = state with MAX(dc:date).
# Coverage: ~100% for Leg17-19, ~0% for Leg13-16 (confirmed 2026-05-28).
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

# Query D — Original presented text URL, cursor-range (MIN versioneTestoAtto by dc:date).
#
# Pipeline confirmed (2026-05-28, diag_camera_stato_testo.py):
#   ocd:atto → ocd:rif_versioneTestoAtto (MIN dc:date) → dcterms:isReferencedBy
#
# IMPORTANT: dc:relation on ocd:atto is NOT the text URL of the act itself.
# It aggregates PDFs for all abbinati (bills in combined discussion): an atto
# with 170 abbinati has 171 distinct dc:relation values (confirmed 2026-05-28).
#
# The returned URL points to getDocumento.ashx. Downloading requires the header:
#   Referer: http://documenti.camera.it/
# (fix confirmed 2026-05-27, test_referer_camera.py).
#
# Results sorted ASC by vta_date; Python keeps the first row per atto
# = version with MIN(dc:date) = original presented text.
# Coverage: ~99% for Leg17-19, ~0.1% for Leg16. Skipped with --no-testo.
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
# Cursor-range fetchers (Queries B, C, D — no VALUES blocks)
# ---------------------------------------------------------------------------

def fetch_natura(luri: str, cursor_start: str, cursor_end: str) -> dict[str, str | None]:
    """Fetch natura label for all atti in the cursor range (Query B).

    Uses FILTER(STR(?atto) > cursor_start && STR(?atto) <= cursor_end) instead
    of a VALUES block — avoids the HTTP 400 that Virtuoso Camera returns for
    specific URI combinations in VALUES blocks (confirmed 2026-05-28, Leg16).

    Returns a dict mapping atto URI → natura label string. Falls back to the
    URI last segment (e.g. 'proposta_legge_ordinaria') when rdfs:label is absent.
    """
    rows = sparql(QUERY_B.format(leg_uri=luri, cursor_start=cursor_start, cursor_end=cursor_end))
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
            # URI last segment as fallback (e.g. "proposta_legge_ordinaria")
            label = nat_uri.rstrip("/").split("/")[-1] or None
        result[a] = label
    return result


def fetch_stato(luri: str, cursor_start: str, cursor_end: str) -> dict[str, tuple[str | None, str | None]]:
    """Fetch the last stato iter for all atti in the cursor range (Query C).

    Returns a dict mapping atto URI → (si_label, si_date_yyyymmdd).
    Query C sorts DESC by si_date; the first row per atto = MAX(si_date).
    """
    rows = sparql(QUERY_C.format(leg_uri=luri, cursor_start=cursor_start, cursor_end=cursor_end))
    result: dict[str, tuple[str | None, str | None]] = {}
    if not rows:
        return result
    for r in rows:
        a = val(r, "atto")
        if not a or a in result:
            # First occurrence per atto = MAX si_date (DESC sort)
            continue
        result[a] = (val(r, "si_label"), val(r, "si_date"))
    return result


def fetch_vta(luri: str, cursor_start: str, cursor_end: str) -> dict[str, tuple[str | None, str | None]]:
    """Fetch the original text URL for all atti in the cursor range (Query D).

    Returns a dict mapping atto URI → (vta_date_yyyymmdd, vta_url).
    Query D sorts ASC by vta_date; the first row per atto = MIN(vta_date)
    = the originally presented text version.
    """
    rows = sparql(QUERY_D.format(leg_uri=luri, cursor_start=cursor_start, cursor_end=cursor_end))
    result: dict[str, tuple[str | None, str | None]] = {}
    if not rows:
        return result
    for r in rows:
        a = val(r, "atto")
        if not a or a in result:
            # First occurrence per atto = MIN vta_date (ASC sort)
            continue
        result[a] = (val(r, "vta_date"), val(r, "vta_url"))
    return result


# ---------------------------------------------------------------------------
# Per-legislature fetch
# ---------------------------------------------------------------------------

def fetch_leg(
    leg: int,
    dry_run: bool = False,
    no_testo: bool = False,
    fetch_ts: str = "",
) -> pd.DataFrame:
    """Fetch all atti for one legislature with full structured metadata.

    Iterates keyset pages of PAGE_SIZE atti (Query A), then for each page runs
    cursor-range Queries B / C / D to fetch natura, stato iter, and text URL.
    Returns a deduplicated DataFrame.

    Queries B/C/D use FILTER(STR(?atto) > prev_cursor && STR(?atto) <= curr_cursor)
    instead of VALUES blocks. This avoids the HTTP 400 that Virtuoso Camera returns
    for specific URI sets in VALUES blocks (confirmed 2026-05-28, Leg16 pages 6+10).
    """
    luri = leg_uri(leg)
    print(f"  [A] Leg{leg} — keyset on STR(?atto)  page_size={PAGE_SIZE}")

    if dry_run:
        q_a = QUERY_A.format(leg_uri=luri, last_atto="", page_size=5)
        print(f"\n  === QUERY A (dry-run, LIMIT 5) ===\n{q_a}")
        if not no_testo:
            ex_start = f"{OCD}attocamera.rdf/ac{leg}_0"
            ex_end   = f"{OCD}attocamera.rdf/ac{leg}_999"
            print(f"  === QUERY D (dry-run, example cursor range) ===\n"
                  f"{QUERY_D.format(leg_uri=luri, cursor_start=ex_start, cursor_end=ex_end)}")
        print("=" * 60)
        return pd.DataFrame()

    all_records: list[dict] = []
    # last_atto: URI cursor for keyset pagination; empty string = before all URIs
    last_atto = ""
    page      = 0

    while True:
        page += 1
        # prev_cursor: the lower bound (exclusive) for sub-queries B/C/D on this page.
        # It equals the cursor that was used to START this page's Query A.
        prev_cursor = last_atto

        rows_a = sparql(QUERY_A.format(leg_uri=luri, last_atto=last_atto, page_size=PAGE_SIZE))

        if not rows_a:
            break

        # Advance the keyset cursor to the largest atto URI on this page.
        # This also serves as the upper bound (inclusive) for sub-queries B/C/D.
        page_attos = [val(r, "atto") for r in rows_a if val(r, "atto")]
        last_atto  = max(page_attos) if page_attos else last_atto

        time.sleep(SLEEP_BETWEEN)
        natura_map = fetch_natura(luri, prev_cursor, last_atto)

        time.sleep(SLEEP_BETWEEN)
        stato_map = fetch_stato(luri, prev_cursor, last_atto)

        vta_map: dict[str, tuple[str | None, str | None]] = {}
        if not no_testo:
            time.sleep(SLEEP_BETWEEN)
            vta_map = fetch_vta(luri, prev_cursor, last_atto)

        # Assemble one record per atto. seen_atto deduplicates any residual
        # duplicates not caught by SELECT DISTINCT in Query A.
        seen: set[str] = set()
        for r in rows_a:
            atto_uri = val(r, "atto")
            if not atto_uri or atto_uri in seen:
                continue
            seen.add(atto_uri)

            # id_atto: URI last segment, e.g. "ac17_1" from attocamera.rdf/ac17_1
            id_atto = atto_uri.rstrip("/").split("/")[-1]
            id_raw  = val(r, "id") or ""
            try:
                id_num = int(id_raw.strip())
            except ValueError:
                id_num = None

            # dc_date: presentation date on the atto (YYYYMMDD, ~100% coverage).
            # Used as fallback for data_presentazione when vta is unavailable.
            dc_date = val(r, "dc_date")

            # Natura from Query B (rdfs:label or URI last segment)
            natura = natura_map.get(atto_uri)

            # Last stato iter from Query C (MAX dc:date via DESC sort + first-row)
            stato_tup      = stato_map.get(atto_uri)
            stato_iter     = stato_tup[0] if stato_tup else None
            data_stato_raw = stato_tup[1] if stato_tup else None

            # Original text URL from Query D (MIN vta dc:date via ASC sort + first-row)
            vta_tup  = vta_map.get(atto_uri)
            vta_date = vta_tup[0] if vta_tup else None
            vta_url  = vta_tup[1] if vta_tup else None

            # data_presentazione: prefer MIN(vta.dc:date) (~99% for Leg17-19);
            # falls back to dc:date on the atto for Leg13-15 and Leg16
            # where versioneTestoAtto coverage is near zero.
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
                # has_testo = True only when an actual URL is available;
                # no_testo mode leaves this False for all atti
                "has_testo":            vta_url is not None,
                "url_scheda_camera":    val(r, "url_scheda"),
                "fonte":                "sparql:dati.camera.it",
                "data_fetch":           fetch_ts,
            })

        print(f"      page={page:>3}  cursor={last_atto.split('/')[-1]:<16}  +{len(seen):>3}  total={len(all_records)}")

        # Fewer rows than PAGE_SIZE signals the last page (DISTINCT + LIMIT applied
        # server-side; if < PAGE_SIZE rows returned, no more data remains)
        if len(rows_a) < PAGE_SIZE:
            break
        time.sleep(SLEEP_BETWEEN)

    if not all_records:
        print(f"  ⚠️  No atti found for Leg{leg}.")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    # Safety-net deduplication on id_atto after all pages are assembled
    before = len(df)
    df = df.drop_duplicates(subset=["id_atto"])
    if len(df) < before:
        print(f"  ℹ️  Deduplicated {before - len(df)} extra id_atto rows.")
    return df


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def build_coverage(df: pd.DataFrame, fetch_ts: str) -> pd.DataFrame:
    """Compute per-legislature coverage statistics from the assembled DataFrame.

    Returns a DataFrame for coverage_camera.parquet.
    """
    if df.empty:
        return pd.DataFrame()

    grp = df.groupby("legislatura", sort=True)
    cov = grp.agg(
        n_atti       = ("id_atto",    "count"),
        n_has_testo  = ("has_testo",  "sum"),
        n_has_natura = ("natura",     lambda x: x.notna().sum()),
        n_has_stato  = ("stato_iter", lambda x: x.notna().sum()),
    ).reset_index()

    cov["pct_has_testo"]  = (cov["n_has_testo"]  / cov["n_atti"] * 100).round(1)
    cov["pct_has_natura"] = (cov["n_has_natura"] / cov["n_atti"] * 100).round(1)
    cov["pct_has_stato"]  = (cov["n_has_stato"]  / cov["n_atti"] * 100).round(1)
    cov["data_fetch"]     = fetch_ts

    # Cast count columns to int (groupby agg can produce float for some pandas versions)
    for col in ["n_atti", "n_has_testo", "n_has_natura", "n_has_stato"]:
        cov[col] = cov[col].astype(int)

    return cov


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Camera dei Deputati legislative act metadata (Leg13-19)."
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
    args = parser.parse_args()

    META_DIR.mkdir(parents=True, exist_ok=True)
    out_atti = META_DIR / "atti_camera.parquet"
    out_cov  = META_DIR / "coverage_camera.parquet"
    out_log  = META_DIR / "fetch_log_camera.json"

    fetch_ts = datetime.now(timezone.utc).isoformat()

    print("fetch_metadati_camera.py")
    print(f"Endpoint   : {SPARQL_ENDPOINT}")
    print(f"Legislature: {args.legs}")
    print(f"Dry-run    : {args.dry_run}")
    print(f"No-testo   : {args.no_testo}")
    print("=" * 60)

    # Leg-level idempotency: always load existing parquet (if present) so that
    # legs NOT being re-fetched are preserved in the merged output.
    # --force only disables the "skip already-present legs" check; it does NOT
    # discard data for other legs. Without this, `--force --legs N` would
    # overwrite the parquet with only leg N, losing all other legislature data.
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
                # Without --force: skip legs already present in the file.
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

    log: list[dict] = []
    all_dfs: list[pd.DataFrame] = []

    for leg in legs_to_fetch:
        print(f"\n── Leg{leg} ──────────────────────────────────────")
        t0 = time.time()

        df = fetch_leg(leg, dry_run=args.dry_run, no_testo=args.no_testo, fetch_ts=fetch_ts)

        if df.empty:
            log.append({"legislatura": leg, "status": "empty", "n_atti": 0})
            continue

        elapsed  = time.time() - t0
        n        = len(df)
        n_testo  = int(df["has_testo"].sum())
        n_natura = int(df["natura"].notna().sum())
        n_stato  = int(df["stato_iter"].notna().sum())
        iniz     = df["iniziativa"].value_counts().head(4).to_dict()

        print(f"\n  ✅ Leg{leg}: {n} atti in {elapsed:.1f}s")
        print(f"     Iniziativa (top 4)   : {iniz}")
        print(f"     Con natura           : {n_natura}/{n} ({n_natura/n*100:.1f}%)")
        print(f"     Con stato iter       : {n_stato}/{n} ({n_stato/n*100:.1f}%)")
        print(f"     Con testo (vta URL)  : {n_testo}/{n} ({n_testo/n*100:.1f}%)")

        log.append({
            "legislatura":  leg,
            "status":       "ok",
            "n_atti":       n,
            "n_has_testo":  n_testo,
            "n_has_natura": n_natura,
            "n_has_stato":  n_stato,
            "elapsed_s":    round(elapsed, 1),
            "fetch_ts":     fetch_ts,
        })

        all_dfs.append(df)
        time.sleep(SLEEP_BETWEEN)

    if args.dry_run or not all_dfs:
        print("\n(dry-run or no data — no files written)")
        return 0

    # ── Merge with existing data for legs not re-fetched ───────────────────
    df_new = pd.concat(all_dfs, ignore_index=True)
    if not df_existing.empty:
        # Retain rows for legs present in the file but not in this run
        legs_new_set = set(df_new["legislatura"].astype(int).unique())
        df_carry     = df_existing[
            ~df_existing["legislatura"].astype(int).isin(legs_new_set)
        ].copy()
        df_all = pd.concat([df_carry, df_new], ignore_index=True)
    else:
        df_all = df_new

    # Enforce canonical column order matching schema §9.2 of CLAUDE.md
    col_order = [
        "id_atto", "id_numerico", "legislatura",
        "titolo", "data_presentazione", "tipo_atto",
        "natura", "iniziativa",
        "stato_iter", "data_stato_iter",
        "url_testo_presentato", "has_testo",
        "url_scheda_camera",
        "fonte", "data_fetch",
    ]
    extra = [c for c in df_all.columns if c not in col_order]
    if extra:
        print(f"\nℹ️  Extra columns found: {extra}")
    df_all = df_all[[c for c in col_order if c in df_all.columns] + extra]
    df_all = df_all.sort_values(["legislatura", "id_numerico"]).reset_index(drop=True)

    # ── Write outputs ───────────────────────────────────────────────────────
    if HAS_PARQUET:
        write_parquet(df_all, out_atti)
        print(f"\n✅ Saved: {out_atti}  ({len(df_all)} rows)")
    else:
        out_atti_csv = out_atti.with_suffix(".csv")
        df_all.to_csv(out_atti_csv, index=False)
        print(f"\n✅ Saved (CSV, duckdb unavailable): {out_atti_csv}  ({len(df_all)} rows)")

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

    # ── JSON log ────────────────────────────────────────────────────────────
    with open(out_log, "w", encoding="utf-8") as f:
        json.dump(
            {"run_ts": fetch_ts, "legs": legs_to_fetch, "results": log},
            f, ensure_ascii=False, indent=2,
        )
    print(f"✅ Log: {out_log}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
