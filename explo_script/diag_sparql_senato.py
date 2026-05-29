#!/usr/bin/env python3
"""
diag_sparql_senato.py — Diagnostica struttura triplestore Senato.
Scopre classi, proprietà e pattern reali per i DDL.

Usage:
  uv run script_prova/diag_sparql_senato.py
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

# ── 1. Classi più popolate ─────────────────────────────────────────────────
print("=" * 60)
print("1. TOP 20 classi nel triplestore")
rows = q("""
SELECT ?cls (COUNT(*) AS ?n)
WHERE { ?s a ?cls }
GROUP BY ?cls ORDER BY DESC(?n) LIMIT 20
""", "classi")
for r in rows:
    print(f"  {v(r,'n'):>8}  {v(r,'cls')}")

time.sleep(1)

# ── 2. Cerca classi con "ddl" o "legge" nel nome ──────────────────────────
print("\n" + "=" * 60)
print("2. Classi con 'ddl', 'legge', 'atto', 'disegno' nel nome")
rows = q("""
SELECT DISTINCT ?cls (COUNT(*) AS ?n)
WHERE { ?s a ?cls }
GROUP BY ?cls
HAVING (
  CONTAINS(LCASE(STR(?cls)), "ddl") ||
  CONTAINS(LCASE(STR(?cls)), "legge") ||
  CONTAINS(LCASE(STR(?cls)), "atto") ||
  CONTAINS(LCASE(STR(?cls)), "disegno")
)
ORDER BY DESC(?n)
""", "classi-ddl")
for r in rows:
    print(f"  {v(r,'n'):>8}  {v(r,'cls')}")

time.sleep(1)

# ── 3. Tutte le proprietà di un DDL campione (se osr:Ddl esiste) ──────────
print("\n" + "=" * 60)
print("3. Proprietà di un'istanza osr:Ddl (se esiste)")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?s WHERE { ?s a osr:Ddl } LIMIT 1
""", "campione-osr:Ddl")
if rows:
    uri = v(rows[0], "s")
    print(f"  URI campione: {uri}")
    props = q(f"SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }}", "props DDL")
    for r in props:
        print(f"  {v(r,'p').split('/')[-1].split('#')[-1]:<30} {v(r,'o')[:80]}")
else:
    print("  osr:Ddl non trovato — provo varianti...")

time.sleep(1)

# ── 4. Cerca "Ddl" in qualsiasi namespace ─────────────────────────────────
print("\n" + "=" * 60)
print("4. Classi che contengono 'Ddl' o 'DDL' (qualsiasi namespace)")
rows = q("""
SELECT DISTINCT ?cls (COUNT(*) AS ?n)
WHERE { ?s a ?cls . FILTER(CONTAINS(STR(?cls), "Ddl") || CONTAINS(STR(?cls), "DDL")) }
GROUP BY ?cls ORDER BY DESC(?n)
""", "Ddl-qualsiasi-ns")
for r in rows:
    print(f"  {v(r,'n'):>8}  {v(r,'cls')}")

time.sleep(1)

# ── 5. Come è collegata la legislatura a oggetti "ddl-like" ───────────────
print("\n" + "=" * 60)
print("5. Oggetti con proprietà osr:legislatura (campione)")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?s ?tipo ?leg
WHERE {
  ?s osr:legislatura ?leg ;
     a ?tipo .
  FILTER(?leg = 19)
}
LIMIT 10
""", "osr:legislatura=19")
for r in rows:
    print(f"  tipo={v(r,'tipo').split('/')[-1]:<20}  leg={v(r,'leg')}  s={v(r,'s')[:60]}")

time.sleep(1)

# ── 6. Prende un oggetto con leg=19 e ne stampa tutte le proprietà ────────
print("\n" + "=" * 60)
print("6. Tutte le proprietà di un oggetto con osr:legislatura=19")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?s WHERE { ?s osr:legislatura 19 } LIMIT 1
""", "campione-leg19")
if rows:
    uri = v(rows[0], "s")
    print(f"  URI: {uri}")
    props = q(f"SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }}", "props-leg19")
    for r in props:
        print(f"  {v(r,'p').split('/')[-1].split('#')[-1]:<30} {v(r,'o')[:80]}")

print("\n" + "=" * 60)
print("Diagnostica completata.")
