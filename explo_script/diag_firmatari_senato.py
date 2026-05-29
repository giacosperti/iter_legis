#!/usr/bin/env python3
"""
diag_firmatari_senato.py — Diagnostic: firmatari (signatories) on osr:Ddl

Investigates whether primo firmatario and co-signatories are available
in the Senato SPARQL triplestore (dati.senato.it), their structure,
coverage per legislature, and how they link to the osr:Senatore entity.

Run with:
    python3 explo_script/diag_firmatari_senato.py 2>&1 | tee /tmp/diag_firmatari_senato.txt

Sections:
  S1 — Full property dump on a sample of Leg17 DDL
       (finds any firmatario-related predicate not yet documented)
  S2 — Search for firmatario-like predicate names across all predicates on osr:Ddl
  S3 — Verify osr:Senatore entity: existence, instance count, available properties
  S4 — Full chain osr:Ddl → firmatario/senatore if found; coverage per legislature
  S5 — Co-signatories: multi-valued count per DDL, distribution

No external dependencies — stdlib urllib only.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import urllib.error
from collections import Counter

ENDPOINT = "https://dati.senato.it/sparql"
HEADERS  = {
    "Accept":     "application/sparql-results+json",
    "User-Agent": "iter-legis-diag/1.0",
}
SLEEP = 1.2   # seconds between queries


def sparql(query: str, timeout: int = 60) -> list[dict]:
    """Execute SPARQL query, return bindings. Prints errors, returns [] on failure."""
    params = urllib.parse.urlencode({
        "query":  query,
        "format": "application/sparql-results+json",
    })
    url = f"{ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("results", {}).get("bindings", [])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"  HTTP {e.code}: {body}")
        return []
    except Exception as e:
        print(f"  Error: {e}")
        return []


def val(b: dict, k: str) -> str | None:
    e = b.get(k)
    return e["value"] if e else None


def sep(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ---------------------------------------------------------------------------
# S1 — Full property dump on 5 sample Leg17 DDL
# ---------------------------------------------------------------------------

sep("S1 — Full property dump: 5 sample Leg17 DDL")
print("Goal: find any predicate that could represent primo firmatario or co-signatories.")
print("Expected from CLAUDE.md §4.1: osr:titolo, osr:dataPresentazione, osr:natura, ...")
print("Looking for: anything with 'firm', 'senat', 'present', 'autore', 'propon', 'sign'")

Q_SAMPLE_DDLS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?ddl WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:idFase ?id .
  FILTER(?id > 0)
}
ORDER BY ?id
LIMIT 5
"""

time.sleep(SLEEP)
sample_ddls = sparql(Q_SAMPLE_DDLS)
ddl_uris = [val(b, "ddl") for b in sample_ddls if val(b, "ddl")]
print(f"\nSample DDL URIs (Leg17, first 5):")
for u in ddl_uris:
    print(f"  {u}")

all_predicates: Counter = Counter()
firmatario_predicates: list[str] = []

for ddl_uri in ddl_uris:
    Q_ALL_PROPS = f"""
SELECT DISTINCT ?pred ?obj WHERE {{
  <{ddl_uri}> ?pred ?obj .
}}
ORDER BY ?pred
"""
    time.sleep(SLEEP)
    rows = sparql(Q_ALL_PROPS)
    print(f"\n  DDL: {ddl_uri.split('/')[-1]} — {len(rows)} triples")
    for r in rows:
        p = val(r, "pred") or ""
        o = val(r, "obj") or ""
        # Shorten URIs for readability
        p_short = p.split("/")[-1].split("#")[-1]
        o_short = o if len(o) < 80 else o[:77] + "..."
        all_predicates[p_short] += 1
        # Flag anything that looks like a signatory
        keywords = ("firm", "senat", "present", "propon", "autor", "sign",
                    "membro", "componente", "deputato", "parlamentar")
        if any(k in p.lower() for k in keywords):
            firmatario_predicates.append(f"{p_short}  →  {o_short}")
        print(f"    {p_short:<35} {o_short}")

print(f"\n--- Predicates that look firmatario-related ---")
if firmatario_predicates:
    for fp in set(firmatario_predicates):
        print(f"  {fp}")
else:
    print("  (none found with keywords: firm, senat, present, propon, autor, sign, membro)")

print(f"\n--- All predicates seen across 5 DDL (sorted by frequency) ---")
for p, n in all_predicates.most_common():
    print(f"  {n}x  {p}")


# ---------------------------------------------------------------------------
# S2 — Search for firmatario-like predicate names in the full ontology
# ---------------------------------------------------------------------------

sep("S2 — Search for firmatario/signatory predicates on osr:Ddl (Leg17, N=100)")
print("Query all distinct predicates used on osr:Ddl in Leg17.")
print("Then filter for anything resembling signatory/author.")

Q_ALL_PREDS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?ddl) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       ?pred ?obj .
}
GROUP BY ?pred
ORDER BY DESC(?n)
LIMIT 80
"""

time.sleep(SLEEP)
rows = sparql(Q_ALL_PREDS)
print(f"\nAll predicates on osr:Ddl (Leg17, top 80 by frequency):")
keywords = ("firm", "senat", "present", "propon", "autor", "sign",
            "membro", "component", "deputato", "parlamentar", "relator",
            "assegn", "commission")
for r in rows:
    p = val(r, "pred") or ""
    n = val(r, "n") or "?"
    p_short = p.split("/")[-1].split("#")[-1]
    flag = " ◄◄◄" if any(k in p.lower() or k in p_short.lower() for k in keywords) else ""
    print(f"  {n:>8}  {p_short}{flag}")


# ---------------------------------------------------------------------------
# S3 — Verify osr:Senatore entity
# ---------------------------------------------------------------------------

sep("S3 — Verify osr:Senatore entity in the triplestore")

Q_COUNT_SEN = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_COUNT_SEN)
n_sen = val(rows[0], "n") if rows else "?"
print(f"\nosr:Senatore instances: {n_sen}")

Q_SEN_PROPS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     ?pred ?obj .
}
GROUP BY ?pred
ORDER BY DESC(?n)
LIMIT 30
"""
time.sleep(SLEEP)
rows = sparql(Q_SEN_PROPS)
print(f"\nProperties on osr:Senatore (top 30 by frequency):")
for r in rows:
    p = val(r, "pred") or ""
    n = val(r, "n") or "?"
    p_short = p.split("/")[-1].split("#")[-1]
    print(f"  {n:>8}  {p_short}")

# Dump a single Senatore instance to see actual values
Q_SEN_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?s ?pred ?obj WHERE {
  ?s a osr:Senatore .
  ?s ?pred ?obj .
}
LIMIT 30
"""
time.sleep(SLEEP)
rows = sparql(Q_SEN_SAMPLE)
if rows:
    sample_uri = val(rows[0], "s") or ""
    print(f"\nSample osr:Senatore: {sample_uri}")
    for r in rows:
        if val(r, "s") == sample_uri:
            p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
            o = val(r, "obj") or ""
            o_short = o if len(o) < 80 else o[:77] + "..."
            print(f"  {p:<35} {o_short}")


# ---------------------------------------------------------------------------
# S4 — Chain osr:Ddl → firmatario/senatore
# ---------------------------------------------------------------------------

sep("S4 — Chain osr:Ddl → Senatore (direct and indirect)")
print("Testing known and candidate predicates for the signatory chain.")

# Test 1: direct osr:firmatario
Q_DIRECT_FIRM = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n_ddl) (COUNT(?link) AS ?n_links) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:firmatario ?link .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_DIRECT_FIRM)
n_ddl = val(rows[0], "n_ddl") if rows else "0"
n_links = val(rows[0], "n_links") if rows else "0"
print(f"\nosr:firmatario (direct on osr:Ddl, Leg17): {n_ddl} DDL, {n_links} links")

# Test 2: osr:presentatoDA or osr:presentatoDa
for prop in ["presentatoDA", "presentatoDa", "presentatoda"]:
    Q_TEST = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n) WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:{prop} ?x .
}}
"""
    time.sleep(SLEEP)
    rows = sparql(Q_TEST)
    n = val(rows[0], "n") if rows else "0"
    print(f"osr:{prop} (Leg17): {n} DDL")

# Test 3: osr:Senatore linked via osr:mandato or similar
Q_SEN_LEG17 = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_SEN_LEG17)
n = val(rows[0], "n") if rows else "0"
print(f"\nosr:Senatore with osr:legislatura=17: {n} instances")

# Test 4: Does osr:Senatore link back to osr:Ddl?
Q_SEN_DDL_LINK = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     ?pred ?obj .
  ?obj a osr:Ddl .
}
GROUP BY ?pred
"""
time.sleep(SLEEP)
rows = sparql(Q_SEN_DDL_LINK)
print(f"\nPredicates from osr:Senatore → osr:Ddl (Leg17):")
if rows:
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
        n = val(r, "n") or "?"
        print(f"  {n:>8}  {p}")
else:
    print("  (no direct link found from Senatore → Ddl)")

# Test 5: Does osr:Ddl link to osr:Senatore via any predicate?
Q_DDL_SEN_LINK = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?ddl) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       ?pred ?s .
  ?s a osr:Senatore .
}
GROUP BY ?pred
"""
time.sleep(SLEEP)
rows = sparql(Q_DDL_SEN_LINK)
print(f"\nPredicates from osr:Ddl → osr:Senatore (Leg17):")
if rows:
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
        n = val(r, "n") or "?"
        print(f"  {n:>8}  {p} ◄◄◄")
else:
    print("  (no direct link found from Ddl → Senatore)")

# Test 6: Intermediate entities — anything between Ddl and Senatore
Q_INTERMEDIATE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?type (COUNT(?x) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       ?pred ?x .
  ?x a ?type .
  FILTER(?type != osr:Ddl)
}
GROUP BY ?type
ORDER BY DESC(?n)
LIMIT 20
"""
time.sleep(SLEEP)
rows = sparql(Q_INTERMEDIATE)
print(f"\nAll entity types reachable from osr:Ddl in one hop (Leg17):")
for r in rows:
    t = (val(r, "type") or "").split("/")[-1].split("#")[-1]
    n = val(r, "n") or "?"
    print(f"  {n:>8}  {t}")


# ---------------------------------------------------------------------------
# S5 — Co-signatories: if any predicate found, count distribution
# ---------------------------------------------------------------------------

sep("S5 — Co-signatories: multi-valued count distribution (Leg17)")
print("If a firmatario predicate was identified in S2/S4, test multi-valued distribution.")
print("Also tests osr:relatore as a proxy for the rapporteur (different from firmatario).")

# osr:relatore — listed in CLAUDE.md §4.1 as a known property, fetch it
Q_RELATORE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n_ddl)
       (COUNT(?rel) AS ?n_links)
WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:relatore ?rel .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_RELATORE)
n_ddl = val(rows[0], "n_ddl") if rows else "0"
n_links = val(rows[0], "n_links") if rows else "0"
print(f"\nosr:relatore (Leg17): {n_ddl} DDL have it, {n_links} total links")

# If relatore exists, dump a sample value
Q_RELATORE_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl ?rel WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:relatore ?rel .
}
LIMIT 5
"""
time.sleep(SLEEP)
rows = sparql(Q_RELATORE_SAMPLE)
if rows:
    print("  Sample osr:relatore values:")
    for r in rows:
        d = (val(r, "ddl") or "").split("/")[-1]
        rel = val(r, "rel") or ""
        print(f"    {d:<20} → {rel}")

# osr:assegnazione — also listed in §4.1 as unfetched property
Q_ASSEGN = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n_ddl) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:assegnazione ?x .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_ASSEGN)
n_assegn = val(rows[0], "n_ddl") if rows else "0"
print(f"\nosr:assegnazione (Leg17): {n_assegn} DDL have it")

# Final summary
sep("SUMMARY")
print("""
Cross-reference findings from S1–S5 to answer:
  1. Does a primo firmatario predicate exist on osr:Ddl?
     → See S2 output (◄◄◄ markers) and S4 direct link tests.

  2. Is the link direct (osr:Ddl → osr:Senatore) or via an intermediate entity?
     → See S4 'Intermediate entities' table.

  3. What properties does osr:Senatore expose?
     → See S3 (name, cognome, gruppo, legislatura, etc.).

  4. Is co-signatory data available and multi-valued?
     → See S5 multi-valued count distribution.

  5. Is osr:relatore the rapporteur (relatore) or the presenter (firmatario)?
     → Check S5 sample values — relatore is expected to be different from firmatario.
""")
