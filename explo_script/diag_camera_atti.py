#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
diag_camera_atti.py — Diagnostica empirica di ocd:atto nel triplestore Camera.
/ Empirical schema exploration of ocd:atto in the Camera dei Deputati SPARQL triplestore.

Risponde alle 4 domande critiche per scrivere fetch_metadati_camera.py:
  Q1. Quanti ocd:atto per legislatura? (verifica conteggi reali)
  Q2. L'endpoint Camera ha un cap Virtuoso come il Senato? (test OFFSET)
  Q3. Qual è il formato dei valori di ocd:rif_leg? (intero o stringa URI?)
  Q4. Quali proprietà ha ocd:atto? (schema empirico completo)
  Q5. C'è una proprietà numerica usabile per keyset pagination?
  Q6. Quali campi chiave per il parquet: titolo, numero, data, stato, tipo?
  Q7. Coverage di ocd:ac (URL testo atto) per legislatura?

Endpoint: https://dati.camera.it/sparql
Prefisso:  ocd: <http://dati.camera.it/ocd/>
URI leg:   http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}
           (confermato da sessioni precedenti — NON usare legislatura/{N})

Usage:
  python3 explo_script/diag_camera_atti.py
  python3 explo_script/diag_camera_atti.py --leg 18   # legislatura campione diversa
  python3 explo_script/diag_camera_atti.py --section 4  # solo sezione 4
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

EP  = "https://dati.camera.it/sparql"
OCD = "http://dati.camera.it/ocd/"

LEGS_ALL    = list(range(13, 20))
LEGS_SAMPLE = [17, 18]   # complete, recent legislatures — use for heavy queries


def leg_uri(n: int) -> str:
    # URI format confirmed empirically (2026-05-27): legislatura.rdf/repubblica_{N}
    # NOT legislatura/{N} — the latter returns 0 results.
    return f"{OCD}legislatura.rdf/repubblica_{n}"


HEADERS = {
    "Accept":     "application/sparql-results+json",
    "User-Agent": "iter-legis-diag/1.0 (camera_atti)",
}


def sparql(query: str, label: str = "", timeout: int = 90, silent: bool = False) -> list[dict]:
    """Execute a SPARQL SELECT query against the Camera endpoint."""
    params = urllib.parse.urlencode({
        "query":  query,
        "format": "application/sparql-results+json",
    })
    req = urllib.request.Request(f"{EP}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("results", {}).get("bindings", [])
            if not silent:
                print(f"  [{label}] → {len(rows)} righe")
            return rows
    except urllib.error.HTTPError as e:
        body = e.read(300).decode("utf-8", errors="replace")
        print(f"  [{label}] HTTP {e.code}: {body[:150]}")
        return []
    except Exception as e:
        print(f"  [{label}] ERRORE: {e}")
        return []


def val(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "") or ""


def sep(n: int, title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  Q{n}. {title}")
    print('=' * 72)


# ── Q1. COUNT ocd:atto per legislatura ────────────────────────────────────────

def q1_counts() -> dict[int, int]:
    """Count ocd:atto per legislatura and verify rif_leg URI format."""
    sep(1, "COUNT ocd:atto per legislatura (Leg13–19)")
    print("  URI leg usato: legislatura.rdf/repubblica_{N}\n")

    counts: dict[int, int] = {}
    for leg in LEGS_ALL:
        leg_u = leg_uri(leg)
        rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(*) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
""", f"Leg{leg}", silent=True)
        n = int(val(rows[0], "n")) if rows else -1
        counts[leg] = n
        flag = "⚠️ " if n == 0 else "✅ "
        print(f"  {flag} Leg{leg}: {n:>8,}")
        time.sleep(0.5)

    # Total without leg filter — detect if rif_leg is mandatory
    rows_tot = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(*) AS ?n)
WHERE { ?s a ocd:atto }
""", "TOTALE senza filtro", silent=True)
    n_tot = int(val(rows_tot[0], "n")) if rows_tot else -1
    print(f"\n  Totale ocd:atto senza filtro: {n_tot:,}")
    print(f"  Somma per leg filtrata:       {sum(v for v in counts.values() if v >= 0):,}")
    print("  (se differiscono: esistono atti senza rif_leg o con leg fuori range)")
    time.sleep(1)
    return counts


# ── Q2. Test cap paginazione OFFSET ───────────────────────────────────────────

def q2_pagination_cap() -> None:
    """Test whether the Camera endpoint enforces a Virtuoso ResultSetMaxRows cap.

    The Senato endpoint caps results at ~10,000 rows per query with LIMIT/OFFSET,
    blocking fetch when OFFSET exceeds the cap. We verify whether Camera behaves
    the same way by probing progressively larger OFFSETs on Leg17.
    """
    sep(2, "Test cap paginazione LIMIT/OFFSET (Leg17)")
    print("  Virtuoso Senato blocca a OFFSET ~10.000. Camera uguale?")
    print("  Probing: OFFSET 0, 500, 1000, 5000, 9000, 10000, 15000, 20000\n")

    leg_u17 = leg_uri(17)
    offsets = [0, 500, 1000, 5000, 9000, 10000, 15000, 20000]

    for offset in offsets:
        rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u17}> .
}}
ORDER BY ?atto
LIMIT 5 OFFSET {offset}
""", f"OFFSET {offset}", silent=True)
        n       = len(rows)
        first   = val(rows[0], "atto").split("/")[-1] if rows else "(vuoto)"
        status  = "✅ OK" if n > 0 else "🔴 VUOTO"
        print(f"  OFFSET {offset:>6}: {status}  n={n}  first={first}")
        time.sleep(0.3)

    print("\n  INTERPRETAZIONE:")
    print("  - Se OFFSET 10000+ restituisce 0: cap confermato → keyset pagination")
    print("  - Se OFFSET 10000+ restituisce risultati: OFFSET libero → paginazione semplice")
    time.sleep(1)


# ── Q3. Formato valori ocd:rif_leg ────────────────────────────────────────────

def q3_leg_format() -> None:
    """Verify the datatype of ocd:rif_leg values on ocd:atto.

    We need to know if ocd:rif_leg holds a URI (xsd:anyURI) or a typed literal
    (xsd:integer) to write correct FILTER clauses in the fetch script.
    """
    sep(3, "Formato valori di ocd:rif_leg su ocd:atto")

    rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT DISTINCT ?leg (DATATYPE(?leg) AS ?dtype)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg ?leg .
}}
LIMIT 10
""", "rif_leg dtype", silent=True)

    if rows:
        print("  Valori di ocd:rif_leg trovati:")
        for r in rows:
            lv = val(r, "leg")
            dt = val(r, "dtype") or "URI (nessun datatype)"
            print(f"    {lv:<60}  dtype={dt}")
    else:
        print("  ⚠️ Nessun risultato — verificare endpoint e URI legislatura")
    time.sleep(1)


# ── Q4. Schema empirico: tutte le proprietà di ocd:atto ──────────────────────

def q4_properties(leg: int = 17) -> None:
    """Enumerate all predicates used on ocd:atto instances in a given legislature.

    Strategy: query DISTINCT predicates with their occurrence count across all
    atti in the legislature. This gives the empirical schema without needing
    to read individual triples for each atto.
    """
    sep(4, f"Schema empirico — tutte le proprietà di ocd:atto (Leg{leg})")
    print("  Conta quante istanze usano ogni predicato (schema empirico).\n")

    leg_u = leg_uri(leg)

    rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT ?prop (COUNT(DISTINCT ?atto) AS ?n_atti) (COUNT(?val) AS ?n_vals)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ?prop ?val .
}}
GROUP BY ?prop
ORDER BY DESC(?n_atti)
""", f"proprietà ocd:atto Leg{leg}", timeout=120)

    if rows:
        print(f"  {'Proprietà':<55}  {'N atti':>8}  {'N vals':>8}")
        print("-" * 75)
        for r in rows:
            p    = val(r, "prop")
            p_s  = p.replace(OCD, "ocd:").replace("http://purl.org/dc/elements/1.1/", "dc:") \
                    .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:") \
                    .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:")
            n_a  = val(r, "n_atti")
            n_v  = val(r, "n_vals")
            print(f"  {p_s:<55}  {n_a:>8}  {n_v:>8}")
    else:
        print("  ⚠️ Nessun risultato — endpoint irraggiungibile?")
    time.sleep(1)


# ── Q4b. Campione 3 atti: dump completo tutte le proprietà ───────────────────

def q4b_sample_dump(leg: int = 17) -> None:
    """Dump all triples for 3 sample atti — sanity check for Q4."""
    sep(4, f"Dump completo di 3 atti campione (Leg{leg})")
    leg_u = leg_uri(leg)

    rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
ORDER BY ?atto
LIMIT 3
""", "URI campione", silent=True)

    if not rows:
        print("  ⚠️ Nessun atto trovato.")
        return

    for sr in rows:
        atto_uri = val(sr, "atto")
        print(f"\n  ── {atto_uri} ──")
        props = sparql(f"SELECT ?p ?o WHERE {{ <{atto_uri}> ?p ?o }}",
                       "dump", silent=True)
        for r in props:
            p_raw = val(r, "p")
            p_s   = p_raw.replace(OCD, "ocd:") \
                          .replace("http://purl.org/dc/elements/1.1/", "dc:") \
                          .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:") \
                          .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:")
            o = val(r, "o")
            print(f"    {p_s:<40}  {o[:85]}")
        time.sleep(0.5)
    time.sleep(1)


# ── Q5. Proprietà candidata per keyset pagination ─────────────────────────────

def q5_keyset_candidates(leg: int = 17) -> None:
    """Identify a property usable as a keyset pagination cursor.

    Requirements for keyset pagination:
      - Exists on (virtually) all atti
      - Values are orderable (numeric or lexicographic)
      - Values are unique or near-unique across the dataset
    Candidates: ocd:id, ocd:numero, ocd:idAtto, dc:identifier, rdfs:label,
    or the URI itself (which is always available and orderable).
    """
    sep(5, f"Proprietà candidata per keyset pagination (Leg{leg})")
    leg_u = leg_uri(leg)

    candidates = [
        ("ocd:id",             f"<{OCD}id>"),
        ("ocd:idAtto",         f"<{OCD}idAtto>"),
        ("ocd:numero",         f"<{OCD}numero>"),
        ("ocd:numeroAtto",     f"<{OCD}numeroAtto>"),
        ("ocd:progressivo",    f"<{OCD}progressivo>"),
        ("dc:identifier",      "<http://purl.org/dc/elements/1.1/identifier>"),
        ("dcterms:identifier", "<http://purl.org/dc/terms/identifier>"),
    ]

    print(f"  {'Proprietà':<30}  {'Coverage':>10}  {'Esempio valore'}")
    print("-" * 75)
    for name, pred in candidates:
        rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n) ?ex
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
  BIND(?val AS ?ex)
}}
LIMIT 1
""", name, silent=True)
        if rows and int(val(rows[0], "n") or 0) > 0:
            ex = val(rows[0], "ex")[:40]
            n  = val(rows[0], "n")
            print(f"  ✅ {name:<28}  {n:>10}  {ex!r}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.3)

    # URI itself as keyset anchor
    rows_uri = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
ORDER BY ?atto
LIMIT 5
""", "URI ordinate", silent=True)
    print(f"\n  Prime 5 URI ordinate di ocd:atto Leg{leg}:")
    for r in rows_uri:
        print(f"    {val(r,'atto')}")
    print("  → URI-based keyset: FILTER(STR(?atto) > '{last_uri}') ORDER BY ?atto")
    time.sleep(1)


# ── Q6. Campi chiave: titolo, numero, data, stato, tipo ─────────────────────

def q6_key_fields(leg: int = 17) -> None:
    """Verify which key metadata fields are available on ocd:atto.

    These are the columns that will populate atti_camera.parquet.
    """
    sep(6, f"Campi chiave per atti_camera.parquet (Leg{leg})")
    leg_u = leg_uri(leg)

    fields = [
        # (name, SPARQL predicate expression)
        ("ocd:titolo",              f"<{OCD}titolo>"),
        ("ocd:numero",              f"<{OCD}numero>"),
        ("ocd:ramo",                f"<{OCD}ramo>"),
        ("ocd:dataPresentazione",   f"<{OCD}dataPresentazione>"),
        ("ocd:dataRicezione",       f"<{OCD}dataRicezione>"),
        ("ocd:rif_tipoAtto",        f"<{OCD}rif_tipoAtto>"),
        ("ocd:rif_statoIter",       f"<{OCD}rif_statoIter>"),
        ("ocd:rif_iter",            f"<{OCD}rif_iter>"),
        ("ocd:ac",                  f"<{OCD}ac>"),
        ("ocd:rif_versioneTestoAtto", f"<{OCD}rif_versioneTestoAtto>"),
        ("ocd:rif_attoCamera",      f"<{OCD}rif_attoCamera>"),
        ("ocd:iniziativa",          f"<{OCD}iniziativa>"),
        ("ocd:rif_iniziativa",      f"<{OCD}rif_iniziativa>"),
        ("ocd:rif_presentatore",    f"<{OCD}rif_presentatore>"),
        ("ocd:rif_proponente",      f"<{OCD}rif_proponente>"),
        ("ocd:rif_trasmissione",    f"<{OCD}rif_trasmissione>"),
        ("dc:title",                "<http://purl.org/dc/elements/1.1/title>"),
        ("rdfs:label",              "<http://www.w3.org/2000/01/rdf-schema#label>"),
        ("dcterms:created",         "<http://purl.org/dc/terms/created>"),
        ("dcterms:modified",        "<http://purl.org/dc/terms/modified>"),
        ("ods:modified",            "<http://open.vocab.org/terms/modified>"),
    ]

    print(f"  {'Campo':<35}  {'N atti':>8}  {'Esempio'}")
    print("-" * 80)
    for name, pred in fields:
        rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n) ?ex
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?ex .
}}
LIMIT 1
""", name, silent=True)
        if rows and int(val(rows[0], "n") or 0) > 0:
            n  = val(rows[0], "n")
            ex = val(rows[0], "ex")[:50]
            print(f"  ✅ {name:<33}  {n:>8}  {ex!r}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.2)
    time.sleep(1)


# ── Q7. Coverage ocd:ac (URL testo atto) per legislatura ─────────────────────

def q7_coverage_ac() -> None:
    """Count atti with ocd:ac (URL to the act text) per legislatura.

    ocd:ac was confirmed in previous sessions as the property holding
    the Camera act URL. This verifies coverage across all legislatures
    to understand how many acts will have a downloadable text.
    """
    sep(7, "Coverage ocd:ac (URL testo atto) per legislatura")

    print(f"  {'Leg':>4}  {'Tot atti':>10}  {'Con ocd:ac':>12}  {'Copertura':>10}")
    print("-" * 45)

    for leg in LEGS_ALL:
        leg_u = leg_uri(leg)

        rows_tot = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
""", f"Leg{leg} tot", silent=True)
        n_tot = int(val(rows_tot[0], "n")) if rows_tot else -1

        rows_ac = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:ac ?url .
}}
""", f"Leg{leg} ac", silent=True)
        n_ac = int(val(rows_ac[0], "n")) if rows_ac else -1

        pct = n_ac / n_tot * 100 if n_tot > 0 and n_ac >= 0 else 0.0
        print(f"  {leg:>4}  {n_tot:>10,}  {n_ac:>12,}  {pct:>9.1f}%")
        time.sleep(0.8)

    # Sample ocd:ac values for Leg17
    leg_u17 = leg_uri(17)
    rows_sample = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto ?url
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u17}> ;
        ocd:ac ?url .
}}
LIMIT 3
""", "campione URL Leg17", silent=True)
    if rows_sample:
        print("\n  Campione URL ocd:ac (Leg17):")
        for r in rows_sample:
            print(f"    {val(r,'atto').split('/')[-1]:<25}  {val(r,'url')[:70]}")
    time.sleep(1)


# ── Q8. Tipo atto — distribuzione per natura/tipoAtto ─────────────────────────

def q8_tipo_atto(leg: int = 17) -> None:
    """Distribution of act types (DDL, PDL, DL, mozione, ecc.) for Leg{leg}.

    Equivalent to osr:natura at Senato. We check ocd:rif_tipoAtto as a
    linked entity and its rdfs:label.
    """
    sep(8, f"Distribuzione tipo atto — ocd:rif_tipoAtto (Leg{leg})")
    leg_u = leg_uri(leg)

    rows = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?tipo ?label (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_tipoAtto ?tipo .
  OPTIONAL {{ ?tipo rdfs:label ?label }}
}}
GROUP BY ?tipo ?label
ORDER BY DESC(?n)
""", f"tipoAtto Leg{leg}", timeout=90)

    if rows:
        print(f"  {'N':>8}  {'Label / URI tipo'}")
        print("-" * 50)
        for r in rows:
            n   = val(r, "n")
            lbl = val(r, "label") or val(r, "tipo").split("/")[-1]
            print(f"  {n:>8}  {lbl[:60]}")
    else:
        print("  ocd:rif_tipoAtto non trovato — tipo atto non disponibile come linked entity")
    time.sleep(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnostica empirica di ocd:atto nel triplestore Camera dei Deputati."
    )
    parser.add_argument("--leg",     type=int, default=17,
                        help="Legislatura campione per sezioni dettagliate (default: 17)")
    parser.add_argument("--section", type=int, default=0,
                        help="Esegui solo questa sezione Q# (0=tutte, default: 0)")
    args = parser.parse_args()

    print("=" * 72)
    print("diag_camera_atti.py — Schema empirico ocd:atto, Camera dei Deputati")
    print(f"Endpoint: {EP}")
    print(f"Legislatura campione: Leg{args.leg}")
    print("=" * 72)

    run = args.section

    if run in (0, 1):  q1_counts()
    if run in (0, 2):  q2_pagination_cap()
    if run in (0, 3):  q3_leg_format()
    if run in (0, 4):  q4_properties(args.leg)
    if run in (0, 4):  q4b_sample_dump(args.leg)
    if run in (0, 5):  q5_keyset_candidates(args.leg)
    if run in (0, 6):  q6_key_fields(args.leg)
    if run in (0, 7):  q7_coverage_ac()
    if run in (0, 8):  q8_tipo_atto(args.leg)

    print(f"\n{'=' * 72}")
    print("Diagnostica completata.")
    print()
    print("PROSSIMI PASSI (dopo aver letto l'output):")
    print("  1. Q1:  riportare i COUNT reali per leg in CLAUDE.md §4.x")
    print("  2. Q2:  se OFFSET>10000 vuoto → keyset pagination obbligatoria")
    print("         se OFFSET>10000 ok    → paginazione semplice sufficiente")
    print("  3. Q4:  riportare le proprietà trovate come colonne parquet")
    print("  4. Q5:  scegliere la proprietà keyset (o URI-based se non ne esiste una)")
    print("  5. Comunicare risultati a Claude → scrivere fetch_metadati_camera.py")


if __name__ == "__main__":
    main()
