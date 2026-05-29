#!/usr/bin/env python3
"""
diag_iniziativa_senato.py — Diagnostic: osr:Iniziativa and osr:primoFirmatario

Targeted follow-up to diag_firmatari_senato.py.
The Senato ontology (confirmed from the index page) exposes:
  - osr:primoFirmatario  — primo firmatario property
  - osr:presentatore     — presenter
  - osr:senatore         — link from osr:Iniziativa to osr:Senatore
  - osr:tipoIniziativa   — initiative type
  - osr:dataAggiuntaFirma / osr:dataRitiroFirma — signature dates
  - osr:gruppo           — parliamentary group

Questions answered here:
  I1 — Does osr:primoFirmatario exist directly on osr:Ddl? What does it return?
  I2 — Full property dump of a sample osr:Iniziativa entity
  I3 — Does osr:Iniziativa have osr:senatore? What is its value type?
  I4 — Does osr:Iniziativa have osr:tipoIniziativa? What are the possible values?
  I5 — Where does osr:gruppo live? (on osr:Senatore? on osr:Iniziativa? on osr:Afferenza?)
  I6 — Coverage of osr:primoFirmatario per legislature (Leg13-19)
  I7 — Multi-valued count of osr:iniziativa per DDL (= total signatories distribution)
  I8 — Full chain: osr:Ddl → osr:primoFirmatario → osr:Senatore. Sample name lookup.

Run with:
    python3 explo_script/diag_iniziativa_senato.py 2>&1 | tee /tmp/diag_iniziativa_senato.txt

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
SLEEP = 1.2


def sparql(query: str, timeout: int = 60) -> list[dict]:
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
# I1 — osr:primoFirmatario directly on osr:Ddl
# ---------------------------------------------------------------------------

sep("I1 — osr:primoFirmatario directly on osr:Ddl (Leg17)")
print("Testing the exact property name from the ontology index.")

Q_PRIMO_ON_DDL = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n_ddl) (COUNT(?pf) AS ?n_links) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:primoFirmatario ?pf .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_PRIMO_ON_DDL)
n_ddl   = val(rows[0], "n_ddl")   if rows else "0"
n_links = val(rows[0], "n_links") if rows else "0"
print(f"\nosr:primoFirmatario on osr:Ddl (Leg17): {n_ddl} DDL, {n_links} links")

# Sample values if it exists
if n_links and int(n_links) > 0:
    Q_PRIMO_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl ?pf WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:primoFirmatario ?pf .
}
LIMIT 5
"""
    time.sleep(SLEEP)
    rows = sparql(Q_PRIMO_SAMPLE)
    print("  Sample values:")
    for r in rows:
        d = (val(r, "ddl") or "").split("/")[-1]
        pf = val(r, "pf") or ""
        print(f"    DDL {d:<10} → {pf}")


# ---------------------------------------------------------------------------
# I2 — Full property dump of a sample osr:Iniziativa entity
# ---------------------------------------------------------------------------

sep("I2 — Full property dump: sample osr:Iniziativa entities (Leg17)")
print("Getting the first few osr:Iniziativa URIs from Leg17 DDL 39302 (multi-firmatari).")

# DDL 39302 = S.5 Leg17, 20 iniziativa links — use it as our test case
SAMPLE_DDL = "http://dati.senato.it/ddl/39302"
Q_GET_INIZ = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?iniz WHERE {{
  <{SAMPLE_DDL}> osr:iniziativa ?iniz .
}}
LIMIT 5
"""
time.sleep(SLEEP)
rows = sparql(Q_GET_INIZ)
iniz_uris = [val(r, "iniz") for r in rows if val(r, "iniz")]
print(f"\nIniciativa URIs for DDL 39302 (first 5):")
for u in iniz_uris:
    print(f"  {u}")

# Dump all properties for each iniziativa entity
for iniz_uri in iniz_uris[:3]:
    Q_INIZ_PROPS = f"""
SELECT ?pred ?obj WHERE {{
  <{iniz_uri}> ?pred ?obj .
}}
ORDER BY ?pred
"""
    time.sleep(SLEEP)
    rows = sparql(Q_INIZ_PROPS)
    iniz_id = iniz_uri.split("/")[-1]
    print(f"\n  osr:Iniziativa {iniz_id} — {len(rows)} triples:")
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
        o = val(r, "obj") or ""
        o_short = o if len(o) < 80 else o[:77] + "..."
        print(f"    {p:<30} {o_short}")


# ---------------------------------------------------------------------------
# I3 — osr:Iniziativa → osr:senatore link structure
# ---------------------------------------------------------------------------

sep("I3 — osr:senatore property on osr:Iniziativa (Leg17)")
print("Checking if osr:senatore on osr:Iniziativa returns osr:Senatore URIs or blank nodes.")

Q_INIZ_SEN = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?iniz) AS ?n_iniz)
       (COUNT(?sen) AS ?n_sen_links)
WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?sen .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_INIZ_SEN)
n_iniz = val(rows[0], "n_iniz") if rows else "0"
n_sen  = val(rows[0], "n_sen_links") if rows else "0"
print(f"\nosr:Iniziativa with osr:senatore (Leg17): {n_iniz} Iniziativa, {n_sen} senatore links")

# Sample: get a senatore URI to verify it's an osr:Senatore entity
Q_INIZ_SEN_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?iniz ?sen WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?sen .
  FILTER(STRSTARTS(STR(?sen), "http://"))
}
LIMIT 5
"""
time.sleep(SLEEP)
rows = sparql(Q_INIZ_SEN_SAMPLE)
if rows:
    print("  Sample osr:senatore values (URI only):")
    for r in rows:
        i = (val(r, "iniz") or "").split("/")[-1]
        s = val(r, "sen") or ""
        print(f"    {i:<35} → {s}")

    # Verify: does the senatore URI correspond to osr:Senatore?
    sample_sen = val(rows[0], "sen") or ""
    if sample_sen:
        Q_VERIFY_SEN = f"""
SELECT ?pred ?obj WHERE {{
  <{sample_sen}> ?pred ?obj .
}}
LIMIT 10
"""
        time.sleep(SLEEP)
        vrows = sparql(Q_VERIFY_SEN)
        print(f"\n  Verification — properties of {sample_sen}:")
        for r in vrows:
            p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
            o = val(r, "obj") or ""
            o_short = o if len(o) < 70 else o[:67] + "..."
            print(f"    {p:<30} {o_short}")


# ---------------------------------------------------------------------------
# I4 — osr:tipoIniziativa values
# ---------------------------------------------------------------------------

sep("I4 — osr:tipoIniziativa values on osr:Iniziativa (Leg17)")

Q_TIPO_INIZ = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?tipo (COUNT(?iniz) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:tipoIniziativa ?tipo .
}
GROUP BY ?tipo
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_TIPO_INIZ)
print(f"\nosr:tipoIniziativa distribution (Leg17):")
if rows:
    for r in rows:
        t = val(r, "tipo") or "?"
        n = val(r, "n") or "?"
        print(f"  {n:>8}  {t}")
else:
    print("  (no results — property may not exist or have different name)")

# Try alternative: tipoIniziativa directly on osr:Ddl
Q_TIPO_DDL = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?tipo (COUNT(?ddl) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:tipoIniziativa ?tipo .
}
GROUP BY ?tipo
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_TIPO_DDL)
print(f"\nosr:tipoIniziativa directly on osr:Ddl (Leg17):")
if rows:
    for r in rows:
        t = val(r, "tipo") or "?"
        n = val(r, "n") or "?"
        print(f"  {n:>8}  {t}")
else:
    print("  (no results)")


# ---------------------------------------------------------------------------
# I5 — Where does osr:gruppo live?
# ---------------------------------------------------------------------------

sep("I5 — osr:gruppo: location in the graph (Leg17)")

# Test 1: on osr:Iniziativa
Q_GRUPPO_INIZ = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?iniz) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:gruppo ?g .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_GRUPPO_INIZ)
n = val(rows[0], "n") if rows else "0"
print(f"\nosr:gruppo on osr:Iniziativa (Leg17): {n} records")

if n and int(n) > 0:
    Q_GRUPPO_INIZ_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?iniz ?g WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:gruppo ?g .
}
LIMIT 5
"""
    time.sleep(SLEEP)
    rows = sparql(Q_GRUPPO_INIZ_SAMPLE)
    print("  Sample values:")
    for r in rows:
        print(f"    {(val(r,'iniz') or '').split('/')[-1]:<35} → {val(r,'g')}")

# Test 2: on osr:Senatore
Q_GRUPPO_SEN = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:gruppo ?g .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_GRUPPO_SEN)
n = val(rows[0], "n") if rows else "0"
print(f"\nosr:gruppo on osr:Senatore: {n} records")

if n and int(n) > 0:
    Q_GRUPPO_SEN_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?s ?g WHERE {
  ?s a osr:Senatore ;
     osr:gruppo ?g .
}
LIMIT 5
"""
    time.sleep(SLEEP)
    rows = sparql(Q_GRUPPO_SEN_SAMPLE)
    print("  Sample values:")
    for r in rows:
        print(f"    {(val(r,'s') or '').split('/')[-1]:<20} → {val(r,'g')}")

# Test 3: on osr:Afferenza (the group membership class)
Q_AFFERENZA = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?a) AS ?n) WHERE {
  ?a a osr:Afferenza .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_AFFERENZA)
n = val(rows[0], "n") if rows else "0"
print(f"\nosr:Afferenza instances: {n}")

if n and int(n) > 0:
    # Dump a sample Afferenza entity
    Q_AFFERENZA_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?a ?pred ?obj WHERE {
  ?a a osr:Afferenza ;
     ?pred ?obj .
}
LIMIT 20
"""
    time.sleep(SLEEP)
    rows = sparql(Q_AFFERENZA_SAMPLE)
    if rows:
        sample_a = val(rows[0], "a") or ""
        print(f"  Sample osr:Afferenza: {sample_a}")
        for r in rows:
            if val(r, "a") == sample_a:
                p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
                o = val(r, "obj") or ""
                print(f"    {p:<30} {o}")


# ---------------------------------------------------------------------------
# I6 — Coverage of primo firmatario chain per legislature (Leg13-19)
# ---------------------------------------------------------------------------

sep("I6 — Coverage per legislature (Leg13-19)")
print("Counting DDL with at least one osr:iniziativa, and Iniziativa with osr:senatore.")

for leg in range(13, 20):
    Q_COV = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT
  (COUNT(DISTINCT ?ddl) AS ?n_ddl)
  (COUNT(DISTINCT ?iniz) AS ?n_iniz)
WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:iniziativa ?iniz .
}}
"""
    time.sleep(SLEEP)
    rows = sparql(Q_COV)
    n_ddl  = val(rows[0], "n_ddl")  if rows else "?"
    n_iniz = val(rows[0], "n_iniz") if rows else "?"

    # Also count how many Iniziativa have osr:senatore
    Q_SEN_COV = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?iniz) AS ?n_with_sen) WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?sen .
}}
"""
    time.sleep(SLEEP)
    rows2 = sparql(Q_SEN_COV)
    n_with_sen = val(rows2[0], "n_with_sen") if rows2 else "?"

    # compute pct if possible
    try:
        pct = f"{int(n_with_sen)/int(n_iniz)*100:.1f}%" if n_iniz and int(n_iniz) > 0 else "n/a"
    except Exception:
        pct = "n/a"

    print(f"  Leg{leg}: {n_ddl:>6} DDL  |  {n_iniz:>7} Iniziativa  |  {n_with_sen:>7} with senatore ({pct})")


# ---------------------------------------------------------------------------
# I7 — Distribution of signatories count per DDL (Leg17)
# ---------------------------------------------------------------------------

sep("I7 — Number of osr:iniziativa per DDL (Leg17) — signatory count distribution")

Q_INIZ_COUNT = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl (COUNT(DISTINCT ?iniz) AS ?n_firmatari) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
}
GROUP BY ?ddl
ORDER BY DESC(?n_firmatari)
LIMIT 200
"""
time.sleep(SLEEP)
rows = sparql(Q_INIZ_COUNT)
counts = [int(val(r, "n_firmatari") or 0) for r in rows]

if counts:
    from collections import Counter
    buckets = Counter()
    for c in counts:
        if c == 1:   buckets["1"]      += 1
        elif c <= 3: buckets["2-3"]    += 1
        elif c <= 5: buckets["4-5"]    += 1
        elif c <= 10: buckets["6-10"]  += 1
        elif c <= 20: buckets["11-20"] += 1
        else:         buckets["21+"]   += 1

    print(f"\nDistribution of firmatari per DDL (Leg17, sample {len(counts)} DDL):")
    for bucket in ["1", "2-3", "4-5", "6-10", "11-20", "21+"]:
        n = buckets.get(bucket, 0)
        bar = "█" * (n // 20)
        print(f"  {bucket:>6} firmatari: {n:>5}  {bar}")
    print(f"\n  Max: {max(counts)}  |  Avg: {sum(counts)/len(counts):.1f}  |  Median: {sorted(counts)[len(counts)//2]}")


# ---------------------------------------------------------------------------
# I8 — Full chain sample: osr:Ddl → osr:Iniziativa → osr:Senatore → name
# ---------------------------------------------------------------------------

sep("I8 — Full chain: DDL → Iniziativa → Senatore → firstName + lastName (Leg17 sample)")
print("Verifying the complete join from DDL to senatore name.")

Q_FULL_CHAIN = """
PREFIX osr:  <http://dati.senato.it/osr/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?ddl ?titolo_breve ?iniz ?tipo ?sen ?nome ?cognome WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?sen .
  OPTIONAL { ?iniz osr:tipoIniziativa ?tipo }
  OPTIONAL { ?sen foaf:firstName ?nome }
  OPTIONAL { ?sen foaf:lastName  ?cognome }
  OPTIONAL { ?ddl osr:titoloBreve ?titolo_breve }
}
ORDER BY ?ddl ?iniz
LIMIT 20
"""
time.sleep(SLEEP)
rows = sparql(Q_FULL_CHAIN)
print(f"\nSample full chain (20 rows):")
current_ddl = None
for r in rows:
    ddl  = (val(r, "ddl")  or "").split("/")[-1]
    iniz = (val(r, "iniz") or "").split("/")[-1]
    tipo = val(r, "tipo")  or ""
    sen  = (val(r, "sen")  or "").split("/")[-1]
    nome = val(r, "nome")  or ""
    cogn = val(r, "cognome") or ""
    titolo = val(r, "titolo_breve") or ""
    if ddl != current_ddl:
        print(f"\n  DDL {ddl} — {titolo[:50]}")
        current_ddl = ddl
    print(f"    {iniz:<35} tipo={tipo:<12} sen={sen:<10} {nome} {cogn}")


# ---------------------------------------------------------------------------
# T1 — Temporal data on osr:Iniziativa: dataAggiuntaFirma / dataRitiroFirma
# ---------------------------------------------------------------------------

sep("T1 — Temporal data on osr:Iniziativa (Leg17)")
print("Checking dataAggiuntaFirma and dataRitiroFirma: coverage and sample values.")
print("These track when each signatory joined or withdrew — key for temporal analysis.")

Q_DATA_FIRMA_COV = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT
  (COUNT(DISTINCT ?iniz) AS ?n_iniz)
  (SUM(IF(BOUND(?daf), 1, 0)) AS ?n_has_aggiunta)
  (SUM(IF(BOUND(?drf), 1, 0)) AS ?n_has_ritiro)
WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  OPTIONAL { ?iniz osr:dataAggiuntaFirma ?daf }
  OPTIONAL { ?iniz osr:dataRitiroFirma   ?drf }
}
"""
time.sleep(SLEEP)
rows = sparql(Q_DATA_FIRMA_COV)
if rows:
    n_iniz   = val(rows[0], "n_iniz")       or "?"
    n_aggiun = val(rows[0], "n_has_aggiunta") or "0"
    n_ritiro = val(rows[0], "n_has_ritiro")   or "0"
    print(f"\n  Total Iniziativa (Leg17): {n_iniz}")
    print(f"  With dataAggiuntaFirma  : {n_aggiun}")
    print(f"  With dataRitiroFirma    : {n_ritiro}")

Q_DATA_FIRMA_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?iniz ?daf ?drf WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  OPTIONAL { ?iniz osr:dataAggiuntaFirma ?daf }
  OPTIONAL { ?iniz osr:dataRitiroFirma   ?drf }
}
LIMIT 10
"""
time.sleep(SLEEP)
rows = sparql(Q_DATA_FIRMA_SAMPLE)
print(f"\n  Sample Iniziativa with temporal data:")
for r in rows:
    i   = (val(r, "iniz") or "").split("/")[-1]
    daf = val(r, "daf") or "(null)"
    drf = val(r, "drf") or "(null)"
    print(f"    {i:<40}  aggiunta={daf}  ritiro={drf}")

# Coverage per legislature
print(f"\n  dataAggiuntaFirma coverage per legislature:")
for leg in range(13, 20):
    Q_COV_LEG = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?iniz) AS ?n_tot) (COUNT(?daf) AS ?n_has) WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:iniziativa ?iniz .
  OPTIONAL {{ ?iniz osr:dataAggiuntaFirma ?daf }}
}}
"""
    time.sleep(SLEEP)
    rows = sparql(Q_COV_LEG)
    n_tot = val(rows[0], "n_tot") if rows else "?"
    n_has = val(rows[0], "n_has") if rows else "?"
    try:
        pct = f"{int(n_has)/int(n_tot)*100:.1f}%" if n_tot and int(n_tot) > 0 else "n/a"
    except Exception:
        pct = "n/a"
    print(f"    Leg{leg}: {n_has}/{n_tot} ({pct})")


# ---------------------------------------------------------------------------
# T2 — osr:FaseIter: date e struttura temporale dell'iter
# ---------------------------------------------------------------------------

sep("T2 — osr:FaseIter: temporal structure of the legislative process (Leg17)")
print("FaseIter traces the timeline: presentation → commission → floor → vote.")
print("Note: GROUP BY on osr:FaseIter returns HTTP 400 (CLAUDE.md §4.8).")
print("Using COUNT without GROUP BY + property dump instead.")

Q_FASEITER_COUNT = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?fi) AS ?n) WHERE {
  ?fi a osr:FaseIter ;
      osr:legislatura 17 .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_FASEITER_COUNT)
n_fi = val(rows[0], "n") if rows else "?"
print(f"\nosr:FaseIter instances (Leg17): {n_fi}")

# Dump all properties of a sample FaseIter
Q_FI_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?fi WHERE {
  ?fi a osr:FaseIter ;
      osr:legislatura 17 .
}
LIMIT 3
"""
time.sleep(SLEEP)
rows = sparql(Q_FI_SAMPLE)
fi_uris = [val(r, "fi") for r in rows if val(r, "fi")]

for fi_uri in fi_uris[:2]:
    Q_FI_PROPS = f"""
SELECT ?pred ?obj WHERE {{
  <{fi_uri}> ?pred ?obj .
}}
ORDER BY ?pred
"""
    time.sleep(SLEEP)
    rows = sparql(Q_FI_PROPS)
    fi_id = fi_uri.split("/")[-1]
    print(f"\n  FaseIter {fi_id} ({len(rows)} triples):")
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
        o = val(r, "obj") or ""
        o_short = o if len(o) < 70 else o[:67] + "..."
        print(f"    {p:<30} {o_short}")

# Check how FaseIter links back to Ddl
Q_FI_DDL_LINK = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?fi) AS ?n) WHERE {
  ?fi a osr:FaseIter ;
      osr:legislatura 17 ;
      ?pred ?ddl .
  ?ddl a osr:Ddl .
}
GROUP BY ?pred
"""
time.sleep(SLEEP)
rows = sparql(Q_FI_DDL_LINK)
print(f"\n  Predicates from FaseIter → Ddl:")
if rows:
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1]
        n = val(r, "n") or "?"
        print(f"    {n:>8}  {p}")
else:
    print("  (none found)")

# Check date-related properties on FaseIter
Q_FI_DATES = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?fi) AS ?n) WHERE {
  ?fi a osr:FaseIter ;
      osr:legislatura 17 ;
      ?pred ?v .
  FILTER(CONTAINS(LCASE(STR(?pred)), "data") ||
         CONTAINS(LCASE(STR(?pred)), "date") ||
         CONTAINS(LCASE(STR(?pred)), "inizio") ||
         CONTAINS(LCASE(STR(?pred)), "fine"))
}
GROUP BY ?pred
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_FI_DATES)
print(f"\n  Date-related predicates on FaseIter (Leg17):")
if rows:
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1]
        n = val(r, "n") or "?"
        print(f"    {n:>8}  {p}")
else:
    print("  (none found with 'data'/'date'/'inizio'/'fine' in name)")

# Coverage per legislature
print(f"\n  FaseIter count per legislature:")
for leg in range(13, 20):
    Q_FI_LEG = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?fi) AS ?n) WHERE {{
  ?fi a osr:FaseIter ;
      osr:legislatura {leg} .
}}
"""
    time.sleep(SLEEP)
    rows = sparql(Q_FI_LEG)
    n = val(rows[0], "n") if rows else "?"
    print(f"    Leg{leg}: {n}")


# ---------------------------------------------------------------------------
# T3 — Amendment temporal data: date via osr:seduta → osr:SedutaAssemblea
# ---------------------------------------------------------------------------

sep("T3 — Amendment date chain (Leg17): Emendamento → seduta → SedutaAssemblea")
print("Amendments have no date directly. Date comes via:")
print("  osr:Emendamento → osr:seduta → osr:SedutaAssemblea → osr:dataSeduta (or similar)")

# Step 1: verify the seduta chain exists
Q_EMEND_SEDUTA = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?emend) AS ?n_emend)
       (COUNT(DISTINCT ?seduta) AS ?n_sedute)
WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:seduta ?seduta .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_EMEND_SEDUTA)
n_emend  = val(rows[0], "n_emend")  if rows else "?"
n_sedute = val(rows[0], "n_sedute") if rows else "?"
print(f"\n  Emendamenti Leg17 with osr:seduta: {n_emend} (out of ~253.387 total)")
print(f"  Distinct sedute: {n_sedute}")

# Step 2: dump properties of a sample SedutaAssemblea
Q_SEDUTA_SAMPLE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?seduta WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:seduta ?seduta .
}
LIMIT 3
"""
time.sleep(SLEEP)
rows = sparql(Q_SEDUTA_SAMPLE)
seduta_uris = [val(r, "seduta") for r in rows if val(r, "seduta")]

for sed_uri in seduta_uris[:2]:
    Q_SED_PROPS = f"""
SELECT ?pred ?obj WHERE {{
  <{sed_uri}> ?pred ?obj .
}}
ORDER BY ?pred
LIMIT 20
"""
    time.sleep(SLEEP)
    rows = sparql(Q_SED_PROPS)
    sed_id = sed_uri.split("/")[-1]
    print(f"\n  SedutaAssemblea {sed_id} ({len(rows)} triples):")
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1].split("#")[-1]
        o = val(r, "obj") or ""
        o_short = o if len(o) < 70 else o[:67] + "..."
        print(f"    {p:<30} {o_short}")

# Step 3: full chain Emendamento → Seduta → data
Q_EMEND_DATE_CHAIN = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?emend ?seduta ?dataSeduta WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:seduta ?seduta .
  OPTIONAL { ?seduta osr:dataSeduta ?dataSeduta }
}
LIMIT 10
"""
time.sleep(SLEEP)
rows = sparql(Q_EMEND_DATE_CHAIN)
print(f"\n  Full chain sample (Emendamento → seduta → dataSeduta):")
for r in rows:
    e = (val(r, "emend") or "").split("/")[-1]
    s = (val(r, "seduta") or "").split("/")[-1]
    d = val(r, "dataSeduta") or "(null)"
    print(f"    {e:<30} → {s:<25} → {d}")

# Step 4: check what date properties exist on SedutaAssemblea
Q_SEDUTA_DATE_PROPS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?s) AS ?n) WHERE {
  ?s a osr:SedutaAssemblea ;
     ?pred ?v .
  FILTER(CONTAINS(LCASE(STR(?pred)), "data") ||
         CONTAINS(LCASE(STR(?pred)), "date") ||
         CONTAINS(LCASE(STR(?pred)), "inizio") ||
         CONTAINS(LCASE(STR(?pred)), "fine"))
}
GROUP BY ?pred
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_SEDUTA_DATE_PROPS)
print(f"\n  Date-related predicates on osr:SedutaAssemblea:")
if rows:
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1]
        n = val(r, "n") or "?"
        print(f"    {n:>8}  {p}")
else:
    print("  (none — try osr:inizio, osr:fine, or generic dc:date)")

# Step 5: also check if SedutaCommissione has date (for commission amendments)
Q_SEDCOM_DATE = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?s) AS ?n) WHERE {
  ?s a osr:SedutaCommissione ;
     ?pred ?v .
  FILTER(CONTAINS(LCASE(STR(?pred)), "data") ||
         CONTAINS(LCASE(STR(?pred)), "inizio") ||
         CONTAINS(LCASE(STR(?pred)), "fine"))
}
GROUP BY ?pred
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_SEDCOM_DATE)
print(f"\n  Date-related predicates on osr:SedutaCommissione:")
if rows:
    for r in rows:
        p = (val(r, "pred") or "").split("/")[-1]
        n = val(r, "n") or "?"
        print(f"    {n:>8}  {p}")
else:
    print("  (none found)")


sep("SUMMARY")
print("""
Key questions answered:
  I1: osr:primoFirmatario directly on osr:Ddl? → see count above
  I2: osr:Iniziativa properties → see dump (look for: senatore, tipoIniziativa,
      primoFirmatario, dataAggiuntaFirma, dataRitiroFirma, gruppo)
  I3: osr:Iniziativa → osr:senatore → URI type? → see verification
  I4: tipoIniziativa values? → distribution table
  I5: osr:gruppo location? → see three tests (Iniziativa / Senatore / Afferenza)
  I6: Coverage per legislature? → critical for deciding fetch strategy
  I7: Firmatari count distribution? → informs column design (array vs separate table)
  I8: Full chain working? → see sample output (nome + cognome)
  T1: dataAggiuntaFirma / dataRitiroFirma coverage and format → signature timeline
  T2: osr:FaseIter structure and date properties → iter timeline
  T3: Amendment date chain Emendamento → SedutaAssemblea → date → confirmed?

Design implications:
  - If osr:primoFirmatario is on osr:Ddl directly → add OPTIONAL to DDL_QUERY
  - If chain goes Ddl → Iniziativa → Senatore → add sub-query E to fetch_metadati_senato.py
  - If coverage for Leg13-15 is low → note in CLAUDE.md (similar to Camera situation)
  - Co-firmatari + temporal data → separate table t_firmatari:
      (id_fase, id_senatore, tipo_iniziativa, ordine, data_aggiunta_firma, data_ritiro_firma)
  - FaseIter dates → table t_fasi_iter: (id_fase, tipo_fase, data_inizio, data_fine, ramo)
  - Amendment dates → derive from seduta.dataSeduta at download time (T5)
""")
