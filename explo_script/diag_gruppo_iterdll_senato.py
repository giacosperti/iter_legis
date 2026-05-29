#!/usr/bin/env python3
"""
diag_gruppo_iterdll_senato.py — Diagnostic: parliamentary group chain, IterDdl, amendment dates

Closes four open questions from previous diagnostics (diag_firmatari_senato.py,
diag_iniziativa_senato.py, 2026-05-28):

  1. Parliamentary group affiliation chain for senators
     Hypothesis: osr:Senatore → osr:mandato → ocd:mandatoSenato → [?] → ocd:adesioneGruppo
                 → osr:gruppo → ocd:gruppoParlamentare
     osr:gruppo has domain ocd:adesioneGruppo (Camera ontology, NOT direct on osr:Senatore).

  2. osr:IterDdl — instances per legislature and property structure
     osr:FaseIter has 0 instances in the triplestore (confirmed 2026-05-28, no date properties
     per ontology); osr:IterDdl is the candidate alternative for iter-structure data.

  3. Amendment → dataSeduta path
     osr:seduta domain is osr:Votazione|osr:Intervento — NOT on osr:Emendamento (confirmed).
     Candidate path: osr:Emendamento → osr:oggetto → osr:OggettoTrattazione → ??? → dataSeduta

  4. osr:Iniziativa senatore coverage puzzle
     Only ~30% of osr:Iniziativa link to osr:senatore; non-parliamentary types account for ~4%.
     Breakdown by tipoIniziativa per legislature needed to explain the gap.

Ontology references (read before modifying queries):
  - Senato: /Users/giacomosperti/Documents/Claude/Ontologie Camere/ontologia_senato.md
  - Camera: /Users/giacomosperti/Documents/Claude/Ontologie Camere/Ontologia_camera.md

Run with:
    python3 explo_script/diag_gruppo_iterdll_senato.py 2>&1 | tee /tmp/diag_gruppo_iterdll.txt

Sections:
  G1 — Dump all properties of osr:mandato entity on sample Leg17 senators
  G2 — From the mandato entity, look for any group-related predicate or adesioneGruppo link
  G3 — Test full chain variants: Senatore → mandato → ??? → gruppo → name
  G4 — If chain found: coverage count Leg17 + group names with senator count
  I1 — osr:IterDdl: count per legislature + property dump on sample
  I2 — Amendment → OggettoTrattazione: dump all properties, look for seduta/date path
  I3 — osr:Iniziativa senatore coverage breakdown by tipoIniziativa and legislature
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import urllib.error

ENDPOINT = "https://dati.senato.it/sparql"
HEADERS = {
    "Accept":     "application/sparql-results+json",
    "User-Agent": "iter-legis-diag/1.0",
}
SLEEP = 1.5   # seconds between queries — be conservative to avoid HTTP 403


def sparql(query: str, timeout: int = 60) -> list[dict]:
    """Execute SPARQL query, return bindings. Prints error and returns [] on failure."""
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


def short(uri: str | None) -> str:
    if not uri:
        return ""
    return uri.split("/")[-1].split("#")[-1] if "/" in uri or "#" in uri else uri


# ---------------------------------------------------------------------------
# G1 — Dump osr:mandato entity on sample Leg17 senators
# ---------------------------------------------------------------------------

sep("G1 — osr:mandato: full property dump on 3 sample Leg17 senators")
print("""
Goal: confirm what osr:mandato links to (blank node? URI? ocd:mandatoSenato?),
and dump all properties of that linked entity.
Hypothesis from ontologia_senato.md: osr:Senatore → osr:mandato → ocd:mandatoSenato.
""")

# Step 1: get 3 sample senators with osr:mandato in Leg17.
# osr:nome / osr:cognome are empirically present but not in the official ontology
# (which documents foaf:firstName/foaf:surname). Use OPTIONAL so missing names
# do not filter out the senator URI.
Q_SAMPLE_SEN = """
PREFIX osr:  <http://dati.senato.it/osr/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT DISTINCT ?s ?nome ?cog WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:mandato ?m .
  OPTIONAL { ?s osr:nome ?nome . }
  OPTIONAL { ?s foaf:firstName ?nome . }
  OPTIONAL { ?s osr:cognome ?cog . }
  OPTIONAL { ?s foaf:surname ?cog . }
}
LIMIT 3
"""
time.sleep(SLEEP)
rows = sparql(Q_SAMPLE_SEN)
print(f"\nSample senators with osr:mandato (Leg17): {len(rows)} found")
sample_senators = []
for r in rows:
    s_uri = val(r, "s") or ""
    nome  = val(r, "nome") or ""
    cog   = val(r, "cog") or ""
    print(f"  {cog} {nome} — {s_uri}")
    sample_senators.append(s_uri)

# Step 2: for each senator, get osr:mandato targets and dump their properties
for s_uri in sample_senators:
    print(f"\n--- Senator: {s_uri.split('/')[-1]} ---")

    # Get all mandato URIs
    Q_MANDATO = f"""
SELECT ?m WHERE {{
  <{s_uri}> <http://dati.senato.it/osr/mandato> ?m .
}}
"""
    time.sleep(SLEEP)
    mandati = sparql(Q_MANDATO)
    if not mandati:
        print("  No osr:mandato found for this senator.")
        continue

    for mr in mandati[:2]:   # at most 2 mandato entities
        m_uri = val(mr, "m") or ""
        print(f"\n  osr:mandato target: {m_uri}")

        # Determine if blank node or URI
        if m_uri.startswith("http"):
            print(f"  Type: Named URI")
            Q_PROPS = f"""
SELECT ?pred ?obj WHERE {{
  <{m_uri}> ?pred ?obj .
}}
ORDER BY ?pred
"""
        else:
            # blank node — use the senator as subject for blank node patterns
            print(f"  Type: Blank node — using senator context")
            Q_PROPS = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?pred ?obj WHERE {{
  <{s_uri}> osr:mandato ?m .
  ?m ?pred ?obj .
}}
ORDER BY ?pred
"""
        time.sleep(SLEEP)
        props = sparql(Q_PROPS)
        print(f"  Properties ({len(props)} triples):")
        for p in props:
            pred = short(val(p, "pred") or "")
            obj  = val(p, "obj") or ""
            obj_short = obj if len(obj) < 80 else obj[:77] + "..."
            print(f"    {pred:<40} {obj_short}")


# ---------------------------------------------------------------------------
# G2 — Search for group-related predicate anywhere reachable from senator
# ---------------------------------------------------------------------------

sep("G2 — Group-related predicates reachable from osr:Senatore in 1-2 hops (Leg17)")
print("""
Enumerate all predicates on osr:Senatore (Leg17) including ocd: namespace.
Then enumerate predicates 2 hops out — looking for adesioneGruppo or gruppoParlamentare.
""")

Q_SEN_ALL_PREDS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     ?pred ?obj .
}
GROUP BY ?pred
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_SEN_ALL_PREDS)
print(f"\nAll predicates on osr:Senatore (Leg17, {len(rows)} distinct predicates):")
group_keywords = ("gruppo", "aderisce", "mandato", "afferenz", "adesion", "partito", "leg")
for r in rows:
    p   = val(r, "pred") or ""
    n   = val(r, "n") or "?"
    p_s = short(p)
    flag = " ◄◄◄" if any(k in p.lower() for k in group_keywords) else ""
    print(f"  {n:>8}  {p_s}{flag}")

# Also test the ocd: namespace directly
print("\n--- Testing ocd: predicates directly on osr:Senatore ---")
for ocd_pred in ["aderisce", "rif_mandatoSenato", "adesioneGruppo"]:
    Q_TEST = f"""
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(?s) AS ?n) WHERE {{
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     ocd:{ocd_pred} ?obj .
}}
"""
    time.sleep(SLEEP)
    rows = sparql(Q_TEST)
    n = val(rows[0], "n") if rows else "0"
    print(f"  ocd:{ocd_pred} on osr:Senatore (Leg17): {n}")


# ---------------------------------------------------------------------------
# G3 — Full chain variant tests: Senatore → mandato → ??? → gruppo
# ---------------------------------------------------------------------------

sep("G3 — Full group chain variant tests (Leg17, COUNT mode)")
print("""
Testing known and plausible chain variants from ontology documentation.
osr:gruppo has domain ocd:adesioneGruppo (Camera ontology, 2026-05-28).
Trying all plausible intermediate steps.
""")

# Variant A: direct osr:Senatore → osr:gruppo
Q_A = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:gruppo ?g .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_A)
print(f"Variant A: osr:Senatore → osr:gruppo (direct): {val(rows[0], 'n') if rows else '?'}")

# Variant B: osr:Senatore → osr:mandato → osr:gruppo
Q_B = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:mandato ?m .
  ?m osr:gruppo ?g .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_B)
print(f"Variant B: osr:Senatore → osr:mandato → osr:gruppo: {val(rows[0], 'n') if rows else '?'}")

# Variant C: osr:Senatore → osr:mandato → ocd:adesioneGruppo → osr:gruppo
Q_C = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:mandato ?m .
  ?m ocd:adesioneGruppo ?ag .
  ?ag osr:gruppo ?g .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_C)
print(f"Variant C: osr:Senatore → osr:mandato → ocd:adesioneGruppo → osr:gruppo: {val(rows[0], 'n') if rows else '?'}")

# Variant D: osr:Senatore → osr:mandato → ocd:aderisce → osr:gruppo
Q_D = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:mandato ?m .
  ?m ocd:aderisce ?ag .
  ?ag osr:gruppo ?g .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_D)
print(f"Variant D: osr:Senatore → osr:mandato → ocd:aderisce → osr:gruppo: {val(rows[0], 'n') if rows else '?'}")

# Variant E: dump all predicates on osr:mandato targets (2 hops from senator)
print("\n--- All predicates on osr:mandato entities (Leg17 senators, N=50 sample) ---")
Q_MANDATO_PREDS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?m) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:mandato ?m .
  ?m ?pred ?obj .
}
GROUP BY ?pred
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_MANDATO_PREDS)
print(f"Predicates found on osr:mandato targets ({len(rows)} distinct):")
for r in rows:
    p = val(r, "pred") or ""
    n = val(r, "n") or "?"
    flag = " ◄◄◄" if any(k in p.lower() for k in group_keywords) else ""
    print(f"  {n:>8}  {short(p)}{flag}")

# Variant F: osr:Afferenza is the class for Commissione/ConsiglioDiPresidenza membership
# (NOT group membership per ontology). Test it anyway to distinguish from group chain.
# osr:Afferenza properties: commissione, organo, carica, fine, inizio — no gruppo.
Q_AFFERENZA_COUNT = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?s) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 .
  ?af a osr:Afferenza .
  ?af ?pred ?s .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_AFFERENZA_COUNT)
print(f"\nVariant F — osr:Afferenza instances linked to Leg17 senators: {val(rows[0], 'n') if rows else '?'}")
print("  (osr:Afferenza = Commissione/ConsiglioDiPresidenza membership, NOT group — for reference only)")


# ---------------------------------------------------------------------------
# G4 — If a working chain was found in G3, get group names + coverage
# ---------------------------------------------------------------------------

sep("G4 — Group chain via osr:mandato: dump entity types reachable in 2 hops")
print("""
From osr:mandato targets, enumerate all entity types reachable in one more hop.
This finds where ocd:adesioneGruppo or ocd:gruppoParlamentare might appear.
""")

Q_TWO_HOP_TYPES = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?type (COUNT(?x) AS ?n) WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:mandato ?m .
  ?m ?pred ?x .
  ?x a ?type .
}
GROUP BY ?type
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_TWO_HOP_TYPES)
print(f"\nEntity types 2 hops from osr:Senatore via osr:mandato (Leg17):")
if rows:
    for r in rows:
        t = short(val(r, "type") or "")
        n = val(r, "n") or "?"
        print(f"  {n:>8}  {t}")
else:
    print("  (no typed entities found at 2 hops)")

# Try sample of the intermediate entities
Q_SAMPLE_MANDATO_OBJ = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?m ?pred ?obj WHERE {
  ?s a osr:Senatore ;
     osr:legislatura 17 ;
     osr:mandato ?m .
  ?m ?pred ?obj .
}
LIMIT 20
"""
time.sleep(SLEEP)
rows = sparql(Q_SAMPLE_MANDATO_OBJ)
if rows:
    print("\n  Sample (mandato_entity, pred, obj) — first 20 triples:")
    for r in rows:
        m   = short(val(r, "m") or "")
        p   = short(val(r, "pred") or "")
        o   = val(r, "obj") or ""
        o_s = o if len(o) < 70 else o[:67] + "..."
        print(f"    {m:<25} {p:<35} {o_s}")


# ---------------------------------------------------------------------------
# I1 — osr:IterDdl: instances per legislature + property dump
# ---------------------------------------------------------------------------

sep("I1 — osr:IterDdl: instance count per legislature + property dump on sample")
print("""
osr:IterDdl is the candidate alternative for iter-structure data.
osr:FaseIter has 0 instances in the triplestore (confirmed 2026-05-28).
Testing if osr:IterDdl has useful coverage and date-related properties.
""")

# osr:IterDdl does NOT have osr:legislatura per ontology (properties: assorbimento,
# testoUnificato, stralcio, fase, idDdl). Filter by legislature via osr:fase → osr:Ddl chain.
print("\nosr:IterDdl instances per legislature (via osr:fase → osr:Ddl → osr:legislatura):")
for leg in [13, 14, 15, 16, 17, 18, 19]:
    Q_COUNT = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{
  ?x a osr:IterDdl ;
     osr:fase ?ddl .
  ?ddl osr:legislatura {leg} .
}}
"""
    time.sleep(SLEEP)
    rows = sparql(Q_COUNT)
    n = val(rows[0], "n") if rows else "?"
    print(f"  Leg{leg}: {n}")

# Total without any filter
Q_COUNT_ALL = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?x) AS ?n) WHERE {
  ?x a osr:IterDdl .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_COUNT_ALL)
print(f"  All legs (no filter): {val(rows[0], 'n') if rows else '?'}")

# Get a sample IterDdl and dump its properties
Q_SAMPLE_ITER = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?x WHERE {
  ?x a osr:IterDdl .
}
LIMIT 3
"""
time.sleep(SLEEP)
rows = sparql(Q_SAMPLE_ITER)
print(f"\nSample osr:IterDdl URIs: {len(rows)} found")
for r in rows:
    x_uri = val(r, "x") or ""
    print(f"  {x_uri}")

    if x_uri.startswith("http"):
        Q_ITER_PROPS = f"""
SELECT ?pred ?obj WHERE {{
  <{x_uri}> ?pred ?obj .
}}
ORDER BY ?pred
"""
    else:
        Q_ITER_PROPS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?x ?pred ?obj WHERE {
  ?x a osr:IterDdl .
  ?x ?pred ?obj .
}
LIMIT 30
"""
    time.sleep(SLEEP)
    props = sparql(Q_ITER_PROPS)
    print(f"  Properties ({len(props)} triples):")
    for p in props[:20]:
        pred = short(val(p, "pred") or "")
        obj  = val(p, "obj") or ""
        o_s  = obj if len(obj) < 80 else obj[:77] + "..."
        print(f"    {pred:<40} {o_s}")

# All distinct predicates on osr:IterDdl
Q_ITER_PREDS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?x) AS ?n) WHERE {
  ?x a osr:IterDdl ;
     ?pred ?obj .
}
GROUP BY ?pred
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_ITER_PREDS)
print(f"\nAll predicates on osr:IterDdl ({len(rows)} distinct):")
date_keywords = ("data", "date", "seduta", "fase", "iter", "ddl", "approv", "present")
for r in rows:
    p = val(r, "pred") or ""
    n = val(r, "n") or "?"
    flag = " ◄◄◄" if any(k in p.lower() or k in short(p).lower() for k in date_keywords) else ""
    print(f"  {n:>8}  {short(p)}{flag}")


# ---------------------------------------------------------------------------
# I2 — Amendment → OggettoTrattazione: full property dump + seduta path
# ---------------------------------------------------------------------------

sep("I2 — Amendment → OggettoTrattazione: property dump + dataSeduta chain")
print("""
osr:seduta domain = osr:Votazione | osr:Intervento (confirmed by ontology).
osr:Emendamento → osr:oggetto → osr:OggettoTrattazione → ??? → dataSeduta
Testing what properties osr:OggettoTrattazione has, and what it links to.
""")

# Get a sample OggettoTrattazione via a Leg17 emendamento
Q_SAMPLE_OT = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?ot WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:oggetto ?ot .
}
LIMIT 3
"""
time.sleep(SLEEP)
rows = sparql(Q_SAMPLE_OT)
print(f"\nSample osr:OggettoTrattazione via emendamento (Leg17): {len(rows)} found")

ot_uris = [val(r, "ot") for r in rows if val(r, "ot")]
for ot_uri in ot_uris:
    print(f"\n  OggettoTrattazione: {ot_uri}")
    if not ot_uri.startswith("http"):
        print("    (blank node — skipping named property query)")
        continue

    Q_OT_PROPS = f"""
SELECT ?pred ?obj WHERE {{
  <{ot_uri}> ?pred ?obj .
}}
ORDER BY ?pred
"""
    time.sleep(SLEEP)
    props = sparql(Q_OT_PROPS)
    print(f"  Properties ({len(props)} triples):")
    for p in props:
        pred = short(val(p, "pred") or "")
        obj  = val(p, "obj") or ""
        o_s  = obj if len(obj) < 80 else obj[:77] + "..."
        flag = " ◄◄◄" if any(k in pred.lower() for k in date_keywords) else ""
        print(f"    {pred:<40} {o_s}{flag}")

# Test 1: OggettoTrattazione → osr:seduta (direct)
Q_OT_SEDUTA = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?ot) AS ?n) WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:oggetto ?ot .
  ?ot osr:seduta ?sed .
}
"""
time.sleep(SLEEP)
rows = sparql(Q_OT_SEDUTA)
print(f"\nOggettoTrattazione → osr:seduta (Leg17): {val(rows[0], 'n') if rows else '?'} OT")

# Test 2: OggettoTrattazione → osr:relativoA → osr:Ddl → seduta/date (already known)
# Test 3: Look for entities reachable from OggettoTrattazione (all types)
Q_OT_TYPES = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?type (COUNT(?ot) AS ?n) WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:oggetto ?ot .
  ?ot ?pred ?x .
  ?x a ?type .
}
GROUP BY ?type
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_OT_TYPES)
print(f"\nEntity types reachable from OggettoTrattazione (Leg17, via 1 hop):")
if rows:
    for r in rows:
        t = short(val(r, "type") or "")
        n = val(r, "n") or "?"
        print(f"  {n:>8}  {t}")
else:
    print("  (no typed entities found)")

# Test 4: All distinct predicates on OggettoTrattazione
Q_OT_PREDS = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?pred (COUNT(?ot) AS ?n) WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:oggetto ?ot .
  ?ot ?pred ?obj .
}
GROUP BY ?pred
ORDER BY DESC(?n)
"""
time.sleep(SLEEP)
rows = sparql(Q_OT_PREDS)
print(f"\nAll predicates on osr:OggettoTrattazione (Leg17, {len(rows)} distinct):")
for r in rows:
    p = val(r, "pred") or ""
    n = val(r, "n") or "?"
    flag = " ◄◄◄" if any(k in p.lower() or k in short(p).lower() for k in date_keywords) else ""
    print(f"  {n:>8}  {short(p)}{flag}")


# ---------------------------------------------------------------------------
# I3 — osr:Iniziativa senatore coverage puzzle: breakdown by tipoIniziativa
# ---------------------------------------------------------------------------

sep("I3 — osr:Iniziativa senatore coverage by tipoIniziativa and legislature")
print("""
Only ~30% of osr:Iniziativa have osr:senatore (confirmed diag_iniziativa_senato.py I6).
Non-parliamentary types account for only ~4% of total Iniziativa — insufficient to explain gap.
Hypothesis 1: the link is there but osr:senatore URI pattern differs across legislatures.
Hypothesis 2: some senatori in older legislatures have no matching entity in the triplestore.
Hypothesis 3: the field is simply not populated for certain records.
""")

# Per legislature: total Iniziativa, with senatore, without senatore, by tipo
print("\nBreakdown by legislature: total iniziativa / with senatore link / without")
for leg in [13, 14, 15, 16, 17, 18, 19]:
    Q_BREAKDOWN = f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT
  (COUNT(?iniz) AS ?n_total)
  (COUNT(?sen)   AS ?n_with_sen)
WHERE {{
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:iniziativa ?iniz .
  OPTIONAL {{ ?iniz osr:senatore ?sen . }}
}}
"""
    time.sleep(SLEEP)
    rows = sparql(Q_BREAKDOWN)
    if rows:
        n_tot = val(rows[0], "n_total") or "0"
        n_sen = val(rows[0], "n_with_sen") or "0"
        try:
            pct = f"{100*int(n_sen)/int(n_tot):.1f}%" if int(n_tot) > 0 else "—"
        except Exception:
            pct = "?"
        print(f"  Leg{leg}: total={n_tot}, with_senatore={n_sen} ({pct})")
    else:
        print(f"  Leg{leg}: no results")
    time.sleep(SLEEP)

# Per tipoIniziativa: aggregate Leg17 — does tipo explain the gap?
print("\nBreakdown by tipoIniziativa (Leg17): total / with senatore")
Q_TIPO = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT
  ?tipo
  (COUNT(?iniz)  AS ?n_total)
  (COUNT(?sen)   AS ?n_with_sen)
WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  OPTIONAL { ?iniz osr:tipoIniziativa ?tipo . }
  OPTIONAL { ?iniz osr:senatore ?sen . }
}
GROUP BY ?tipo
ORDER BY DESC(?n_total)
"""
time.sleep(SLEEP)
rows = sparql(Q_TIPO)
print(f"  (Leg17, grouped by tipoIniziativa):")
for r in rows:
    tipo  = val(r, "tipo") or "(null)"
    n_tot = val(r, "n_total") or "0"
    n_sen = val(r, "n_with_sen") or "0"
    try:
        pct = f"{100*int(n_sen)/int(n_tot):.1f}%" if int(n_tot) > 0 else "—"
    except Exception:
        pct = "?"
    print(f"    {tipo:<20} total={n_tot:>6}, with_sen={n_sen:>6} ({pct})")

# Investigate: for Parlamentare Iniziativa without senatore — does osr:presentatore exist?
# (it always should — this tests whether the field is merely not linked, vs not populated)
Q_PARLAMENTARE_NO_SEN = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT
  (COUNT(?iniz) AS ?n_no_sen)
  (COUNT(?pres) AS ?n_has_presentatore)
WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:tipoIniziativa "Parlamentare" .
  FILTER NOT EXISTS { ?iniz osr:senatore ?sen . }
  OPTIONAL { ?iniz osr:presentatore ?pres . }
}
"""
time.sleep(SLEEP)
rows = sparql(Q_PARLAMENTARE_NO_SEN)
if rows:
    n_no  = val(rows[0], "n_no_sen") or "0"
    n_pre = val(rows[0], "n_has_presentatore") or "0"
    print(f"\n  Leg17 Parlamentare WITHOUT osr:senatore: {n_no}")
    print(f"  Of those, WITH osr:presentatore: {n_pre} (name string present but no entity link)")

# Sample: show some Parlamentare Iniziativa without senatore
Q_SAMPLE_NO_SEN = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?iniz ?pres ?pf WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:tipoIniziativa "Parlamentare" .
  OPTIONAL { ?iniz osr:presentatore ?pres . }
  OPTIONAL { ?iniz osr:primoFirmatario ?pf . }
  FILTER NOT EXISTS { ?iniz osr:senatore ?sen . }
}
LIMIT 10
"""
time.sleep(SLEEP)
rows = sparql(Q_SAMPLE_NO_SEN)
if rows:
    print(f"\n  Sample Parlamentare Iniziativa WITHOUT senatore (first 10):")
    for r in rows:
        iniz = short(val(r, "iniz") or "")
        pres = val(r, "pres") or "(no presentatore)"
        pf   = val(r, "pf") or "(no primoFirmatario)"
        print(f"    {iniz:<20} pres={pres:<30} pf={pf}")


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

sep("SUMMARY — Cross-reference findings to close open questions")
print("""
G1–G4: Parliamentary group chain
  ✓/✗  osr:Senatore → osr:mandato → ??? verified?
       → Check G1 (what osr:mandato links to)
       → Check G3 variants (which returned > 0 results)
       → Check G4 (entity types 2 hops out)

I1: osr:IterDdl
  ✓/✗  Has instances? Has date properties?
       → See instance count per leg + predicate dump

I2: Amendment date chain
  ✓/✗  OggettoTrattazione has osr:seduta or date properties?
       → See OT property dump and entity types
       → If no path found, date of amendment requires a different approach
         (e.g. join via osr:Votazione where the amendment was voted on)

I3: osr:Iniziativa senatore coverage
  ✓/✗  Is the ~70% gap explained by tipoIniziativa breakdown?
       → See per-type and per-leg tables
       → If Parlamentare still has < 100%, the link is simply absent
         (not populated for older records or non-Senato initiators)
""")
