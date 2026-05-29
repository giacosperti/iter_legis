#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
diag_count_reale_leg13_14.py — Verifica il conteggio reale di DDL nel triplestore
per tutte le legislature, usando query COUNT (non soggette al cap di riga dell'endpoint).

Obiettivo: capire se le 10.000 righe di Leg13 e Leg14 (e le 3.000 di Leg16)
nel parquet sono un troncamento da cap dell'endpoint, o il numero reale.

Una query COUNT restituisce un singolo numero aggregato → bypassa qualsiasi
limite sul numero di righe restituite dall'endpoint.

Usage:
  uv run explo_script/diag_count_reale_leg13_14.py
"""

import json
import time
import urllib.parse
import urllib.request

EP = "https://dati.senato.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}

# Righe nel parquet — per confronto diretto
PARQUET_COUNTS = {13: 10000, 14: 10000, 15: 5568, 16: 3000, 17: 8004, 18: 6479, 19: 4913}


def sparql(query: str, label: str = "", timeout: int = 60) -> list[dict]:
    params = urllib.parse.urlencode({"query": query,
                                     "format": "application/sparql-results+json"})
    req = urllib.request.Request(f"{EP}?{params}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rows = json.loads(r.read())["results"]["bindings"]
            if label:
                print(f"  [{label}] → {len(rows)} righe di risposta")
            return rows
    except Exception as e:
        print(f"  [{label}] ERRORE: {e}")
        return []


def v(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "")


print("=" * 65)
print("Conteggio reale DDL nel triplestore Senato — tutte le legislature")
print("Query COUNT: bypassano il cap sul numero di righe dell'endpoint")
print("=" * 65)

results = []

for leg in range(13, 20):
    print(f"\n── Leg{leg} ─────────────────────────────────────────")

    # 1. Conteggio totale istanze osr:Ddl
    rows = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(?ddl) AS ?n)
WHERE {{ ?ddl a osr:Ddl ; osr:legislatura {leg} }}
""", f"COUNT totale Leg{leg}")
    n_totale = int(v(rows[0], "n")) if rows else -1

    # 2. Conteggio DDL unici per idDdl
    rows2 = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?id_ddl) AS ?n)
WHERE {{ ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:idDdl ?id_ddl }}
""", f"COUNT DISTINCT idDdl Leg{leg}")
    n_unici = int(v(rows2[0], "n")) if rows2 else -1

    # 3. Conteggio prime fasi (progressivoIter = 1)
    # Nota: il letterale deve essere tipizzato come xsd:integer per matchare
    rows3 = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT (COUNT(?ddl) AS ?n)
WHERE {{ ?ddl a osr:Ddl ; osr:legislatura {leg} ;
              osr:progressivoIter "1"^^xsd:integer }}
""", f"COUNT progressivoIter=1 Leg{leg}")
    n_prime = int(v(rows3[0], "n")) if rows3 else -1

    parquet_n   = PARQUET_COUNTS.get(leg, "?")
    troncato    = (n_totale > parquet_n) if isinstance(parquet_n, int) and n_totale >= 0 else None
    delta       = (n_totale - parquet_n) if isinstance(parquet_n, int) and n_totale >= 0 else "?"

    risultato = {
        "leg":       leg,
        "n_totale":  n_totale,
        "n_unici":   n_unici,
        "n_prime":   n_prime,
        "parquet_n": parquet_n,
        "troncato":  troncato,
        "mancanti":  delta,
    }
    results.append(risultato)

    flag = "⚠️  TRONCATO" if troncato else ("✅ completo" if troncato is False else "?")
    print(f"  Triplestore → totale={n_totale}  unici={n_unici}  prime_fasi={n_prime}")
    print(f"  Parquet     → {parquet_n} righe")
    print(f"  Delta       → {delta} righe mancanti  {flag}")

    time.sleep(1.5)

# ---------------------------------------------------------------------------
# Riepilogo finale
# ---------------------------------------------------------------------------

print("\n" + "=" * 65)
print("RIEPILOGO")
print("=" * 65)
print(f"{'Leg':>4}  {'Triplestore':>12}  {'Unici':>8}  {'Parquet':>8}  {'Mancanti':>9}  Stato")
print("-" * 65)
for r in results:
    flag = "⚠️ TRONCATO" if r["troncato"] else ("✅" if r["troncato"] is False else "?")
    print(f"  {r['leg']:>2}  {r['n_totale']:>12,}  {r['n_unici']:>8,}  "
          f"{r['parquet_n']:>8}  {r['mancanti']:>9}  {flag}")

print()
troncate = [r["leg"] for r in results if r["troncato"]]
if troncate:
    print(f"Legislature con dataset incompleto: Leg{troncate}")
    print()
    print("AZIONE NECESSARIA: rieseguire fetch_metadati_senato.py per queste")
    print("legislature con una strategia che bypassa il cap, ad esempio:")
    print("  - Suddividere la query per ramo (ramo=S + ramo=C separatamente)")
    print("  - Suddividere per range di idFase (es. FILTER(?id_fase < 5000))")
    print("  - Usare ORDER BY + sub-query per paginazione deterministica")
else:
    print("Nessun troncamento rilevato — dataset completo per tutte le legislature.")
