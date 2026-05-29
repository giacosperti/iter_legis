#!/usr/bin/env python3
"""
diag_emendamenti_senato.py — Scopre come osr:Emendamento è collegato a osr:Ddl.

Usage:
  uv run explo_script/diag_emendamenti_senato.py
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

# ── 1. Prendi un emendamento campione Leg17 ───────────────────────────────
print("=" * 60)
print("1. Campione osr:Emendamento Leg17 — tutte le proprietà")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?emend WHERE { ?emend a osr:Emendamento ; osr:legislatura 17 }
LIMIT 1
""", "campione-emend-leg17")

if rows:
    uri = v(rows[0], "emend")
    print(f"  URI: {uri}")
    props = q(f"SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }}", "props-emend")
    for r in props:
        p = v(r,'p').split('/')[-1].split('#')[-1]
        print(f"  {p:<30} {v(r,'o')[:80]}")

time.sleep(1)

# ── 2. Cerca proprietà che puntano a URI ddl/ ─────────────────────────────
print("\n" + "=" * 60)
print("2. Proprietà di osr:Emendamento che contengono 'ddl' nel valore")
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?p (SAMPLE(?o) AS ?es)
WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         ?p ?o .
  FILTER(CONTAINS(STR(?o), "/ddl/") || CONTAINS(LCASE(STR(?p)), "ddl"))
}
GROUP BY ?p
""", "prop-con-ddl")
for r in rows:
    print(f"  {v(r,'p').split('/')[-1]:<30} es: {v(r,'es')[:70]}")

time.sleep(1)

# ── 3. Conta emendamenti per un DDL specifico (Leg17, idFase noto) ────────
print("\n" + "=" * 60)
print("3. Emendamenti collegati a un DDL campione Leg17")

# Prima prendi un DDL Leg17
rows_ddl = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl ?id_fase ?numero_fase WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:progressivoIter 1 ;
       osr:numeroFase ?numero_fase .
  OPTIONAL { ?ddl osr:idFase ?id_fase }
}
LIMIT 3
""", "campione-ddl-leg17")

for r in rows_ddl:
    ddl_uri = v(r, "ddl")
    num     = v(r, "numero_fase")
    print(f"\n  DDL: {ddl_uri}  numero={num}")

    # Prova diverse proprietà di collegamento
    for prop in ["osr:idFaseDdl", "osr:ddl", "osr:riferimentoDdl",
                 "osr:fase", "osr:idDdl", "osr:idFase"]:
        cnt = q(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(*) AS ?n) WHERE {{
  ?emend a osr:Emendamento ;
         {prop} <{ddl_uri}> .
}}
""", f"count via {prop}")
        n = v(cnt[0], "n") if cnt else "0"
        if n != "0":
            print(f"  ✅ {prop} → {n} emendamenti")
        else:
            print(f"  ✗  {prop} → 0")
    time.sleep(0.3)

time.sleep(1)

# ── 4. Verifica con idFase numerico invece di URI ─────────────────────────
print("\n" + "=" * 60)
print("4. Verifica collegamento via valore numerico idFase")
rows_ddl2 = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl ?id_fase WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:progressivoIter 1 ;
       osr:idFase ?id_fase .
}
LIMIT 3
""", "ddl-con-idFase")

for r in rows_ddl2:
    id_fase = v(r, "id_fase")
    print(f"\n  idFase={id_fase}")
    cnt = q(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(*) AS ?n) WHERE {{
  ?emend a osr:Emendamento ;
         osr:idFase {id_fase} .
}}
""", f"emend con idFase={id_fase}")
    n = v(cnt[0], "n") if cnt else "0"
    print(f"  → {n} emendamenti via osr:idFase={id_fase}")

print("\n" + "=" * 60)
print("Diagnostica completata.")
