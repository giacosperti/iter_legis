#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "pyarrow"]
# ///
"""
diag_emend_count_gap.py — Verifica il gap tra i conteggi emendamenti
nel parquet (atti_senato.parquet) e i totali reali nel triplestore.

Domanda: la differenza tra triplestore e parquet è spiegata solo dal
filtro ramo=S / prime_fasi, o c'è anche un problema di troncamento
nella EMEND_COUNT_QUERY?

Strategia:
  1. Dal parquet: somma n_emendamenti per tutti i DDL (tutti rami e fasi)
     → confronta con totale triplestore
  2. Dal parquet: breakdown per (ramo, is_prima_fase)
     → capisce quanta parte della differenza è filtro vs troncamento
  3. Query COUNT dirette sul triplestore per ramo=S/C e prime fasi
     → verifica se il problema è nella query di conteggio o nel join

Usage:
  uv run explo_script/diag_emend_count_gap.py
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

EP = "https://dati.senato.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}

# Totali triplestore da diag_emend_formati.py
TRIPLESTORE_TOTALS = {13: 709, 14: 86147, 15: 33652, 16: 116909,
                      17: 253387, 18: 151262, 19: 53337}


def sparql(query: str, label: str = "", timeout: int = 90) -> list[dict]:
    params = urllib.parse.urlencode({"query": query,
                                     "format": "application/sparql-results+json"})
    req = urllib.request.Request(f"{EP}?{params}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rows = json.loads(r.read())["results"]["bindings"]
            if label:
                print(f"    [{label}] → {len(rows)} righe")
            return rows
    except Exception as e:
        print(f"    [{label}] ERRORE: {e}")
        return []


def v(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "") or ""


# ---------------------------------------------------------------------------
# Parte 1 — Analisi del parquet
# ---------------------------------------------------------------------------

print("=" * 70)
print("PARTE 1 — Breakdown emendamenti nel parquet per legislatura")
print("=" * 70)

parquet_path = Path("data/meta/atti_senato.parquet")
if not parquet_path.exists():
    csv = parquet_path.with_suffix(".csv")
    df = pd.read_csv(csv, dtype={"n_emendamenti": int}) if csv.exists() else None
else:
    df = pd.read_parquet(parquet_path)

if df is None:
    print("❌ Parquet non trovato.")
    raise SystemExit(1)

# Assicuriamoci che n_emendamenti sia numerico
df["n_emendamenti"] = pd.to_numeric(df["n_emendamenti"], errors="coerce").fillna(0).astype(int)
df["is_prima_fase"] = df["is_prima_fase"].astype(bool)

print(f"Parquet caricato: {len(df)} righe\n")

parquet_summary = []

for leg in range(13, 20):
    sub = df[df["legislatura"] == leg]
    ts_tot = TRIPLESTORE_TOTALS.get(leg, 0)

    # Totale nel parquet (tutti rami, tutte fasi)
    tot_parquet = sub["n_emendamenti"].sum()

    # Breakdown per ramo × is_prima_fase
    breakdown = sub.groupby(["ramo_origine", "is_prima_fase"])["n_emendamenti"].sum().reset_index()
    breakdown.columns = ["ramo", "prima_fase", "n_emend"]

    rS_p1 = breakdown.query("ramo=='S' and prima_fase==True")["n_emend"].sum()
    rS_p2 = breakdown.query("ramo=='S' and prima_fase==False")["n_emend"].sum()
    rC_p1 = breakdown.query("ramo=='C' and prima_fase==True")["n_emend"].sum()
    rC_p2 = breakdown.query("ramo=='C' and prima_fase==False")["n_emend"].sum()

    gap = ts_tot - tot_parquet
    pct_cov = tot_parquet / ts_tot * 100 if ts_tot else 0

    print(f"── Leg{leg} ───────────────────────────────────────────────")
    print(f"  Triplestore (reale)   : {ts_tot:>10,}")
    print(f"  Parquet (tutti)       : {tot_parquet:>10,}  ({pct_cov:.1f}% coverage)")
    print(f"  Gap                   : {gap:>10,}")
    print(f"  Breakdown parquet:")
    print(f"    ramo=S, prime_fasi  : {int(rS_p1):>10,}")
    print(f"    ramo=S, fasi succ.  : {int(rS_p2):>10,}")
    print(f"    ramo=C, prime_fasi  : {int(rC_p1):>10,}")
    print(f"    ramo=C, fasi succ.  : {int(rC_p2):>10,}")
    print()

    parquet_summary.append({
        "leg": leg, "ts_tot": ts_tot, "parquet_tot": int(tot_parquet),
        "gap": int(gap), "pct_cov": round(pct_cov, 1),
        "rS_p1": int(rS_p1), "rS_p2": int(rS_p2),
        "rC_p1": int(rC_p1), "rC_p2": int(rC_p2),
    })

# ---------------------------------------------------------------------------
# Parte 2 — Verifica COUNT triplestore per ramo e prime fasi
# ---------------------------------------------------------------------------

print("=" * 70)
print("PARTE 2 — Verifica COUNT triplestore per ramo (Leg16 e Leg17)")
print("           (le più significative per dimensione e completezza)")
print("=" * 70)

for leg in [16, 17]:
    print(f"\n── Leg{leg} ───────────────────────────────────────────────")

    # Count emendamenti per ramo del DDL
    for ramo in ["S", "C"]:
        r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?emend) AS ?n)
WHERE {{
  ?emend a osr:Emendamento ; osr:legislatura {leg} ;
         osr:oggetto ?ogg .
  ?ogg osr:relativoA ?ddl .
  ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:ramo "{ramo}" .
}}
""", f"COUNT emend ramo={ramo} Leg{leg}")
        n = int(v(r[0], "n")) if r else -1
        print(f"  Emendamenti collegati a DDL ramo={ramo}: {n:>10,}")
        time.sleep(1)

    # Count emendamenti per prime fasi (progressivoIter=1)
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT (COUNT(DISTINCT ?emend) AS ?n)
WHERE {{
  ?emend a osr:Emendamento ; osr:legislatura {leg} ;
         osr:oggetto ?ogg .
  ?ogg osr:relativoA ?ddl .
  ?ddl a osr:Ddl ; osr:legislatura {leg} ;
       osr:progressivoIter "1"^^xsd:integer .
}}
""", f"COUNT emend progressivoIter=1 Leg{leg}")
    n = int(v(r[0], "n")) if r else -1
    print(f"  Emendamenti su prime fasi (iter=1)  : {n:>10,}")
    time.sleep(1)

    # Count emendamenti NON collegati ad alcun DDL (orfani)
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?emend) AS ?n)
WHERE {{
  ?emend a osr:Emendamento ; osr:legislatura {leg} .
  FILTER NOT EXISTS {{
    ?emend osr:oggetto ?ogg .
    ?ogg osr:relativoA ?ddl .
    ?ddl a osr:Ddl .
  }}
}}
""", f"COUNT emend orfani (no DDL link) Leg{leg}")
    n = int(v(r[0], "n")) if r else -1
    print(f"  Emendamenti senza DDL collegato     : {n:>10,}  ← potrebbero spiegare il gap")
    time.sleep(1)

# ---------------------------------------------------------------------------
# Parte 3 — Riepilogo finale
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("RIEPILOGO — Gap parquet vs triplestore")
print("=" * 70)
print(f"{'Leg':>4}  {'Triplestore':>12}  {'Parquet':>10}  {'Gap':>8}  {'Cov%':>6}  "
      f"{'rS_p1':>8}  {'rC_p1':>8}")
print("-" * 70)
for r in parquet_summary:
    print(f"  {r['leg']:>2}  {r['ts_tot']:>12,}  {r['parquet_tot']:>10,}  "
          f"{r['gap']:>8,}  {r['pct_cov']:>5.1f}%  "
          f"{r['rS_p1']:>8,}  {r['rC_p1']:>8,}")

print()
print("Ipotesi sul gap:")
print("  A) Il gap è spiegato da emendamenti orfani (no link DDL nel triplestore)")
print("  B) Il gap è spiegato da DDL ramo=C che hanno emendamenti Senato")
print("     ma la EMEND_COUNT_QUERY li mappa su DDL diversi da quelli nel parquet")
print("  C) La EMEND_COUNT_QUERY ha un suo problema di troncamento/paginazione")
print()
print("  → Guardare 'Emendamenti senza DDL collegato' in Parte 2:")
print("    Se orfani ≈ gap → ipotesi A (emendamenti non collegabili a DDL)")
print("    Se orfani ≈ 0   → ipotesi B o C (problema di join o paginazione)")
