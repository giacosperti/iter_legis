#!/usr/bin/env python3
"""
diag_oggetto_trattazione.py — Esplora la catena di collegamento
  osr:Emendamento → osr:oggetto → osr:OggettoTrattazione → osr:Ddl

Usage:
  uv run explo_script/diag_oggetto_trattazione.py
"""
import json, time, urllib.parse, urllib.request

EP = "https://dati.senato.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}

def q(query, label=""):
    params = urllib.parse.urlencode({"query": query, "format": "application/sparql-results+json"})
    req = urllib.request.Request(f"{EP}?{params}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read())["results"]["bindings"]
            print(f"\n[{label}] → {len(rows)} righe")
            return rows
    except Exception as e:
        print(f"\n[{label}] ERRORE: {e}")
        return []

def v(b, k): return b.get(k, {}).get("value", "")

# ── 1. Tutte le proprietà di OggettoTrattazione 775705 ───────────────────
print("=" * 60)
print("1. Proprietà di oggettotrattazione/775705")
OGG_URI = "http://dati.senato.it/oggettotrattazione/775705"
rows = q(f"SELECT ?p ?o WHERE {{ <{OGG_URI}> ?p ?o }}", "props-oggetto")
for r in rows:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    print(f"  {p:<30} {v(r,'o')[:80]}")

time.sleep(1)

# ── 2. Chi punta a OggettoTrattazione 775705 (relazioni inverse) ──────────
print("\n" + "=" * 60)
print("2. Soggetti che puntano a oggettotrattazione/775705")
rows = q(f"""
SELECT ?s ?p WHERE {{
  ?s ?p <{OGG_URI}> .
}}
LIMIT 10
""", "inverse-oggetto")
for r in rows:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    print(f"  {v(r,'s')[:60]}  via  {p}")

time.sleep(1)

# ── 3. Prendi un DDL Leg17 e segui la catena verso emendamenti ────────────
print("\n" + "=" * 60)
print("3. Catena DDL → ??? → Emendamento per un DDL Leg17")

# Prendi un DDL con emendamenti noti (proviamo con un iter avanzato)
rows_ddl = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl ?fase ?idFase WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:fase ?fase .
  OPTIONAL { ?ddl osr:idFase ?idFase }
}
LIMIT 5
""", "ddl-leg17-campione")
for r in rows_ddl:
    print(f"  ddl={v(r,'ddl').split('/')[-1]}  fase={v(r,'fase')}  idFase={v(r,'idFase')}")

time.sleep(1)

# ── 4. Cerca emendamenti tramite catena DDL → oggetto → emendamento ───────
print("\n" + "=" * 60)
print("4. Conta emendamenti via catena: ?ddl ← ?ogg ← ?emend (Leg17)")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl (COUNT(DISTINCT ?emend) AS ?n)
WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         osr:oggetto ?ogg .
  ?ogg ?p ?ddl .
  ?ddl a osr:Ddl ;
       osr:legislatura 17 .
}
GROUP BY ?ddl
ORDER BY DESC(?n)
LIMIT 5
""", "emend-via-oggetto-catena")
for r in rows:
    print(f"  ddl={v(r,'ddl').split('/')[-1]}  n_emend={v(r,'n')}")

time.sleep(1)

# ── 5. Proprietà di OggettoTrattazione — top predicati usati ─────────────
print("\n" + "=" * 60)
print("5. Predicati più usati su osr:OggettoTrattazione")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?p (COUNT(*) AS ?n) (SAMPLE(?o) AS ?es)
WHERE {
  ?ogg a osr:OggettoTrattazione ;
       ?p ?o .
}
GROUP BY ?p ORDER BY DESC(?n) LIMIT 15
""", "predicati-oggetto")
for r in rows:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    print(f"  {v(r,'n'):>8}  {p:<30} es: {v(r,'es')[:50]}")

time.sleep(1)

# ── 6. OggettoTrattazione campione — tutte le proprietà ──────────────────
print("\n" + "=" * 60)
print("6. Tutte le proprietà di un OggettoTrattazione Leg17")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ogg WHERE { ?ogg a osr:OggettoTrattazione }
LIMIT 1
""", "ogg-campione")
if rows:
    uri = v(rows[0], "ogg")
    print(f"  URI: {uri}")
    props = q(f"SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }}", "props-ogg-campione")
    for r in props:
        p = v(r,'p').split('/')[-1].split('#')[-1]
        print(f"  {p:<30} {v(r,'o')[:80]}")

print("\n" + "=" * 60)
print("Diagnostica completata.")
