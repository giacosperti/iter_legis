#!/usr/bin/env python3
"""
diag_date_temporali.py — Esplora la struttura temporale del triplestore Senato.

Verifica quali campi data sono disponibili su:
  - osr:Emendamento       (data presentazione emendamento)
  - osr:FaseIter          (date delle fasi dell'iter legislativo)
  - osr:Votazione         (date e risultati delle votazioni)
  - osr:SedutaCommissione (date delle sedute in commissione)

Obiettivo: capire se è possibile ricostruire la timeline completa
  presentazione DDL → commissione → aula → voto finale
e fare join temporali con le affiliazioni parlamentari
(per sapere in quale gruppo era un senatore in un dato momento).

Usage:
  uv run explo_script/diag_date_temporali.py
"""
import json, time, urllib.parse, urllib.request

EP = "https://dati.senato.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}

def q(query, label="", timeout=30):
    params = urllib.parse.urlencode({"query": query, "format": "application/sparql-results+json"})
    req = urllib.request.Request(f"{EP}?{params}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rows = json.loads(r.read())["results"]["bindings"]
            print(f"\n[{label}] → {len(rows)} righe")
            return rows
    except Exception as e:
        print(f"\n[{label}] ERRORE: {e}")
        return []

def v(b, k): return b.get(k, {}).get("value", "")

def dump_props(uri, label):
    rows = q(f"SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }}", label)
    for r in rows:
        p = v(r,'p').split('/')[-1].split('#')[-1]
        print(f"    {p:<30} {v(r,'o')[:80]}")
    return rows

# ═══════════════════════════════════════════════════════════════════════════
# 1. osr:Emendamento — campi data
# ═══════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("1. osr:Emendamento — campi data disponibili (Leg17)")

# Campione ampio per vedere tutti i predicati usati
rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?p (SAMPLE(?o) AS ?es) (COUNT(*) AS ?n)
WHERE {
  ?emend a osr:Emendamento ;
         osr:legislatura 17 ;
         ?p ?o .
}
GROUP BY ?p ORDER BY DESC(?n)
""", "predicati-emendamento-leg17")
for r in rows:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    es = v(r,'es')
    n  = v(r,'n')
    flag = " ◀ DATA?" if any(x in p.lower() for x in ["data","date","inizio","fine","quando","time"]) else ""
    print(f"  {n:>8}  {p:<30} es: {es[:45]}{flag}")

time.sleep(1)

# Campione di emendamento con tutti i campi
print("\n  --- Proprietà complete di 3 emendamenti campione ---")
rows3 = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?emend WHERE { ?emend a osr:Emendamento ; osr:legislatura 17 }
LIMIT 3
""", "3-emend-campione")
for r in rows3:
    uri = v(r, "emend")
    print(f"\n  URI: {uri}")
    dump_props(uri, f"props {uri.split('/')[-1]}")
    time.sleep(0.3)

time.sleep(1)

# ═══════════════════════════════════════════════════════════════════════════
# 2. osr:FaseIter — struttura e campi data
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. osr:FaseIter — struttura e campi data (Leg17)")

rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?p (SAMPLE(?o) AS ?es) (COUNT(*) AS ?n)
WHERE {
  ?fase a osr:FaseIter ;
        osr:legislatura 17 ;
        ?p ?o .
}
GROUP BY ?p ORDER BY DESC(?n)
""", "predicati-faseiter-leg17")
for r in rows:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    es = v(r,'es')
    n  = v(r,'n')
    flag = " ◀ DATA?" if any(x in p.lower() for x in ["data","date","inizio","fine","quando","time"]) else ""
    print(f"  {n:>8}  {p:<30} es: {es[:45]}{flag}")

time.sleep(1)

# Campione FaseIter collegato a un DDL
print("\n  --- FaseIter di un DDL campione ---")
rows_fi = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?fase ?ddl WHERE {
  ?fase a osr:FaseIter ;
        osr:legislatura 17 ;
        osr:relativoA ?ddl .
  ?ddl a osr:Ddl .
}
LIMIT 1
""", "faseiter-con-ddl")
if rows_fi:
    uri = v(rows_fi[0], "fase")
    ddl = v(rows_fi[0], "ddl")
    print(f"  FaseIter: {uri}")
    print(f"  DDL:      {ddl}")
    dump_props(uri, "props-faseiter")

time.sleep(1)

# ═══════════════════════════════════════════════════════════════════════════
# 3. osr:Votazione — struttura e campi data/risultato
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. osr:Votazione — struttura e campi data/risultato (Leg17)")

rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?p (SAMPLE(?o) AS ?es) (COUNT(*) AS ?n)
WHERE {
  ?vot a osr:Votazione ;
       osr:legislatura 17 ;
       ?p ?o .
}
GROUP BY ?p ORDER BY DESC(?n)
""", "predicati-votazione-leg17")
for r in rows:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    es = v(r,'es')
    n  = v(r,'n')
    flag = " ◀ DATA?" if any(x in p.lower() for x in ["data","date","inizio","fine","quando","time"]) else ""
    flag2 = " ◀ ESITO?" if any(x in p.lower() for x in ["esito","result","approv","voto","favor","contr"]) else ""
    print(f"  {n:>8}  {p:<30} es: {es[:45]}{flag}{flag2}")

time.sleep(1)

# Campione Votazione
print("\n  --- Proprietà complete di una Votazione campione ---")
rows_v = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?vot WHERE { ?vot a osr:Votazione ; osr:legislatura 17 }
LIMIT 1
""", "votazione-campione")
if rows_v:
    uri = v(rows_v[0], "vot")
    print(f"  URI: {uri}")
    dump_props(uri, "props-votazione")

time.sleep(1)

# ═══════════════════════════════════════════════════════════════════════════
# 4. osr:SedutaCommissione — struttura e campi data
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. osr:SedutaCommissione — struttura e campi data (Leg17)")

rows = q("""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?p (SAMPLE(?o) AS ?es) (COUNT(*) AS ?n)
WHERE {
  ?sed a osr:SedutaCommissione ;
       osr:legislatura 17 ;
       ?p ?o .
}
GROUP BY ?p ORDER BY DESC(?n)
""", "predicati-sedutacommissione-leg17")
for r in rows:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    es = v(r,'es')
    n  = v(r,'n')
    flag = " ◀ DATA?" if any(x in p.lower() for x in ["data","date","inizio","fine","quando","time"]) else ""
    print(f"  {n:>8}  {p:<30} es: {es[:45]}{flag}")

time.sleep(1)

# ═══════════════════════════════════════════════════════════════════════════
# 5. Ricostruzione timeline completa per un DDL campione
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. Timeline completa per un DDL Leg17 con emendamenti")

# Prendo un DDL con molti emendamenti (es. ddl/44128 dal risultato precedente)
DDL_URI = "http://dati.senato.it/ddl/44128"
print(f"  DDL: {DDL_URI}")

# Data presentazione DDL
rows_ddl = q(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?p ?o WHERE {{ <{DDL_URI}> ?p ?o }}
""", "ddl-44128-props")
for r in rows_ddl:
    p = v(r,'p').split('/')[-1].split('#')[-1]
    if any(x in p.lower() for x in ["data","fase","stato","titolo","ramo","numero","progressivo"]):
        print(f"    {p:<30} {v(r,'o')[:70]}")

time.sleep(1)

# FaseIter collegate a questo DDL
rows_fi2 = q(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?fase ?p ?o
WHERE {{
  ?fase a osr:FaseIter ;
        osr:relativoA <{DDL_URI}> ;
        ?p ?o .
}}
ORDER BY ?fase
LIMIT 30
""", "faseiter-ddl-44128")
fasi = {}
for r in rows_fi2:
    fase = v(r,'fase')
    p    = v(r,'p').split('/')[-1].split('#')[-1]
    o    = v(r,'o')
    if fase not in fasi:
        fasi[fase] = {}
    fasi[fase][p] = o
print(f"\n  FaseIter trovate: {len(fasi)}")
for uri, props in list(fasi.items())[:5]:
    print(f"    {uri.split('/')[-1]}: " +
          "  ".join(f"{k}={v[:30]}" for k,v in props.items() if k not in ["type"]))

time.sleep(1)

# Votazioni collegate
rows_vot2 = q(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?vot ?p ?o
WHERE {{
  ?vot a osr:Votazione ;
       osr:oggetto ?ogg ;
       ?p ?o .
  ?ogg osr:relativoA <{DDL_URI}> .
}}
LIMIT 20
""", "votazioni-ddl-44128")
voti = {}
for r in rows_vot2:
    vot  = v(r,'vot')
    p    = v(r,'p').split('/')[-1].split('#')[-1]
    o    = v(r,'o')
    if vot not in voti:
        voti[vot] = {}
    voti[vot][p] = o
print(f"\n  Votazioni trovate: {len(voti)}")
for uri, props in list(voti.items())[:3]:
    print(f"    {uri.split('/')[-1]}: " +
          "  ".join(f"{k}={v[:30]}" for k,v in props.items() if k not in ["type"]))

print("\n" + "=" * 60)
print("Diagnostica completata.")
