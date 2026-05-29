#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
diag_camera_emendamenti.py — Esplora gli emendamenti Camera tramite la catena
ocd:allegatoDiscussione, confermata dall'ontologia ufficiale (v1.2).

Catena ontologica (fonte: http://dati.camera.it/ocd/ v1.2):
  ocd:atto
    ← ocd:rif_attoCamera (domain: ocd:dibattito, range: ocd:atto)
  ocd:dibattito
    → ocd:rif_discussione (domain: ocd:dibattito, range: ocd:discussione)
  ocd:discussione
    → ocd:rif_allegatoDiscussione (domain: ocd:discussione, range: ocd:allegatoDiscussione)
  ocd:allegatoDiscussione  ← qui si trovano (presumibilmente) gli emendamenti

Struttura:
  PARTE 1 — Conta gli allegatoDiscussione totali nel triplestore
  PARTE 2 — Proprietà disponibili su allegatoDiscussione (schema empirico)
  PARTE 3 — Filtra allegati che sembrano emendamenti (via label / tipo)
  PARTE 4 — Campione URL degli allegati emendamento per capire il formato
  PARTE 5 — Verifica la catena completa atto → allegato su un atto campione
  PARTE 6 — Conta allegatoDiscussione per legislatura (usando rif_leg su dibattito)

Endpoint: https://dati.camera.it/sparql
Prefisso: ocd: <http://dati.camera.it/ocd/>

Usage:
  uv run explo_script/diag_camera_emendamenti.py
"""

import json
import time
import urllib.parse
import urllib.request

EP = "https://dati.camera.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}


def sparql(query: str, label: str = "", timeout: int = 90) -> list[dict]:
    params = urllib.parse.urlencode({"query": query,
                                     "format": "application/sparql-results+json"})
    req = urllib.request.Request(f"{EP}?{params}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rows = json.loads(r.read())["results"]["bindings"]
            if label:
                print(f"  [{label}] → {len(rows)} righe")
            return rows
    except Exception as e:
        print(f"  [{label}] ERRORE: {e}")
        return []


def v(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "") or ""


# ─────────────────────────────────────────────────────────────────────────────
# PARTE 1 — Conta allegatoDiscussione totali
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("PARTE 1 — Conteggio ocd:allegatoDiscussione nel triplestore Camera")
print("=" * 72)

r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(DISTINCT ?all) AS ?n)
WHERE { ?all a ocd:allegatoDiscussione }
""", "COUNT allegatoDiscussione totale")

if r:
    print(f"  ocd:allegatoDiscussione totali: {v(r[0], 'n')}")
else:
    print("  (nessun risultato)")

time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 2 — Proprietà disponibili su allegatoDiscussione
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 2 — Proprietà disponibili su ocd:allegatoDiscussione (schema empirico)")
print("=" * 72)

r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?prop (COUNT(?all) AS ?n)
WHERE {
  ?all a ocd:allegatoDiscussione ;
       ?prop ?val .
}
GROUP BY ?prop
ORDER BY DESC(?n)
LIMIT 30
""", "props allegatoDiscussione")

if r:
    print(f"  {'Proprietà':<60}  {'Count':>8}")
    print("-" * 72)
    for row in r:
        prop = v(row, "prop")
        n    = v(row, "n")
        print(f"  {prop:<60}  {n:>8}")
else:
    print("  (nessun risultato)")

time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 3 — Campione completo di un allegatoDiscussione
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 3 — Campione di 3 allegatoDiscussione con tutte le proprietà")
print("=" * 72)

r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?all ?prop ?val
WHERE {
  ?all a ocd:allegatoDiscussione ;
       ?prop ?val .
  FILTER(?all IN (
    <http://dati.camera.it/ocd/allegatoDiscussione/leg17ADL0001.xml>,
    <http://dati.camera.it/ocd/allegatoDiscussione/leg18ADL0001.xml>
  ))
}
LIMIT 40
""", "campione URI noti")

if not r:
    # Se gli URI non esistono, prendi i primi disponibili
    r_ids = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?all
WHERE { ?all a ocd:allegatoDiscussione }
LIMIT 3
""", "primi 3 URI")

    if r_ids:
        ids = [v(row, "all") for row in r_ids]
        filter_str = ", ".join(f"<{i}>" for i in ids)
        r = sparql(f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?all ?prop ?val
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ?prop ?val .
  FILTER(?all IN ({filter_str}))
}}
""", "campione props")

if r:
    current = None
    for row in r:
        uri  = v(row, "all").split("/")[-1]
        prop = v(row, "prop").split("/")[-1]
        val  = v(row, "val")
        if uri != current:
            print(f"\n  ── {uri} ──")
            current = uri
        print(f"    {prop:<30} = {val[:90]}")

time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 4 — Allegati con "emend" nella label o nel tipo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 4 — Allegati con 'emend' nel contenuto (label / tipo / URI)")
print("=" * 72)

# Via rdfs:label
r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT (COUNT(DISTINCT ?all) AS ?n)
WHERE {
  ?all a ocd:allegatoDiscussione ;
       rdfs:label ?label .
  FILTER(CONTAINS(LCASE(?label), "emend"))
}
""", "COUNT label=emend")
if r:
    print(f"  Allegati con rdfs:label contenente 'emend': {v(r[0], 'n')}")

time.sleep(0.8)

# Via URI pattern
r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(DISTINCT ?all) AS ?n)
WHERE {
  ?all a ocd:allegatoDiscussione .
  FILTER(CONTAINS(LCASE(STR(?all)), "emend"))
}
""", "COUNT URI=emend")
if r:
    print(f"  Allegati con 'emend' nell'URI:              {v(r[0], 'n')}")

time.sleep(0.8)

# Campione URI con emend
r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?all ?label ?url
WHERE {
  ?all a ocd:allegatoDiscussione .
  OPTIONAL { ?all rdfs:label ?label }
  OPTIONAL { ?all ocd:urlFile ?url }
  FILTER(CONTAINS(LCASE(STR(?all)), "emend") || CONTAINS(LCASE(?label), "emend"))
}
LIMIT 8
""", "campione allegati emend")

if r:
    print("\n  Campione URI allegati emendamento:")
    for row in r:
        uri   = v(row, "all")
        label = v(row, "label")
        url   = v(row, "url")
        ext   = url.rsplit(".", 1)[-1].split("?")[0].lower() if url else "?"
        print(f"  URI  : {uri[:90]}")
        if label: print(f"  label: {label[:80]}")
        if url:   print(f"  url  : [{ext}] {url[:90]}")
        print()
else:
    print("  (nessun allegato con 'emend' trovato via label/URI)")

time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 5 — Catena completa atto → allegatoDiscussione (verifica su Leg17/18)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 5 — Catena atto → dibattito → discussione → allegatoDiscussione")
print("          (campione Leg18, primi 5 atti con allegati)")
print("=" * 72)

r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?atto ?dibattito ?discussione ?allegato
WHERE {
  ?dibattito a ocd:dibattito ;
             ocd:rif_leg <http://dati.camera.it/ocd/legislatura/18> ;
             ocd:rif_attoCamera ?atto ;
             ocd:rif_discussione ?discussione .
  ?discussione ocd:rif_allegatoDiscussione ?allegato .
}
LIMIT 5
""", "catena atto→allegato Leg18")

if r:
    for row in r:
        atto      = v(row, "atto").split("/")[-1]
        dibattito = v(row, "dibattito").split("/")[-1]
        discussione = v(row, "discussione").split("/")[-1]
        allegato  = v(row, "allegato").split("/")[-1]
        print(f"  atto={atto}  dibattito={dibattito}  discuss={discussione}  allegato={allegato}")
else:
    print("  (catena non trovata con questa struttura)")
    # Prova variante: seduta → discussione
    r2 = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?atto ?discussione ?allegato
WHERE {
  ?discussione a ocd:discussione ;
               ocd:rif_allegatoDiscussione ?allegato ;
               ocd:rif_attoCamera ?atto .
}
LIMIT 5
""", "discussione → atto (diretto)")
    if r2:
        for row in r2:
            atto = v(row, "atto").split("/")[-1]
            disc = v(row, "discussione").split("/")[-1]
            all_ = v(row, "allegato").split("/")[-1]
            print(f"  atto={atto}  discussione={disc}  allegato={all_}")
    else:
        print("  (variante diretta non trovata — proprietà diversa?)")

time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 6 — Conteggio allegatoDiscussione per legislatura
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 6 — Conteggio allegatoDiscussione per legislatura (Leg13–19)")
print("=" * 72)
print(f"  {'Leg':>4}  {'N allegati':>12}")
print("-" * 22)

for leg in range(13, 20):
    leg_uri = f"http://dati.camera.it/ocd/legislatura/{leg}"
    r = sparql(f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(DISTINCT ?allegato) AS ?n)
WHERE {{
  ?dibattito a ocd:dibattito ;
             ocd:rif_leg <{leg_uri}> ;
             ocd:rif_discussione ?discussione .
  ?discussione ocd:rif_allegatoDiscussione ?allegato .
}}
""", f"COUNT allegati Leg{leg}")
    n = v(r[0], "n") if r else "?"
    print(f"  {leg:>4}  {n:>12}")
    time.sleep(1)

print()
print("=" * 72)
print("Fine diagnostica Camera emendamenti")
print("=" * 72)
print()
print("INTERPRETAZIONE:")
print("  - Se COUNT allegatoDiscussione >> 0: la catena funziona")
print("  - Verificare in PARTE 2 quale proprietà contiene l'URL del file")
print("    (cercate 'url', 'ac', 'file', 'testo' tra le proprietà emerse)")
print("  - Verificare in PARTE 4 se gli emendamenti hanno un pattern URI")
print("    riconoscibile (es. 'emend' nell'URI o in rdfs:label)")
print("  - Il formato URL (PARTE 4) determina la pipeline di download")
