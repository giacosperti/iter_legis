#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "pyarrow"]
# ///
"""
diag_testi_ddl.py — Diagnostica copertura testi DDL nel parquet e nel triplestore.

Analizza i tre predicati principali sul testo dei DDL:
  - osr:testoPresentato  → URN del testo originale depositato dal proponente
  - osr:testoApprovato   → URN del testo votato/approvato in quella fase
  - osr:testoUnificato   → URN del testo risultante da fusione di più DDL

Struttura in tre parti:
  PARTE 1 — Copertura dal parquet (has_testo_presentato / has_testo_approvato)
             per legislatura, ramo e progressivoIter
  PARTE 2 — Copertura testoUnificato dal triplestore (COUNT SPARQL per leg)
  PARTE 3 — Campione di URN testo_presentato per capire il pattern URL
             e verificare se è uniforme tra legislature/rami

Domande a cui risponde:
  1. Quanti DDL hanno il testo presentato disponibile? (per leg e ramo)
  2. Quanti DDL hanno il testo approvato disponibile? (per leg)
  3. Quanti DDL hanno un testo unificato? (fonte: triplestore)
  4. Qual è il pattern degli URN? (niR, URL diretto, o misto?)
  5. I DDL ramo=C hanno testo_presentato lato Senato?

Usage:
  uv run explo_script/diag_testi_ddl.py
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

EP = "https://dati.senato.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}
PARQUET = Path("data/meta/atti_senato.parquet")


def sparql(query: str, label: str = "", timeout: int = 60) -> list[dict]:
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
# PARTE 1 — Analisi dal parquet
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("PARTE 1 — Copertura testi DDL nel parquet (atti_senato.parquet)")
print("=" * 72)

if not PARQUET.exists():
    print(f"❌ Parquet non trovato: {PARQUET}")
    raise SystemExit(1)

df = pd.read_parquet(PARQUET)
print(f"Parquet caricato: {len(df):,} righe, {df['legislatura'].nunique()} legislature\n")

# Assicura tipi corretti
for col in ["has_testo_presentato", "has_testo_approvato"]:
    if col in df.columns:
        df[col] = df[col].fillna(False).astype(bool)
    else:
        print(f"  ⚠️  Colonna '{col}' non presente nel parquet — salto.")

# ── Copertura globale per legislatura ────────────────────────────────────────
print("── Copertura per legislatura (tutti i rami) ────────────────────────────")
print(f"{'Leg':>4}  {'Tot DDL':>8}  {'has_pres':>9}  {'%pres':>6}  "
      f"{'has_appr':>9}  {'%appr':>6}")
print("-" * 55)

summary = []
for leg in range(13, 20):
    sub = df[df["legislatura"] == leg]
    tot = len(sub)
    n_pres = sub["has_testo_presentato"].sum() if "has_testo_presentato" in sub else 0
    n_appr = sub["has_testo_approvato"].sum()  if "has_testo_approvato"  in sub else 0
    pct_pres = n_pres / tot * 100 if tot else 0
    pct_appr = n_appr / tot * 100 if tot else 0
    print(f"  {leg:>2}  {tot:>8,}  {int(n_pres):>9,}  {pct_pres:>5.1f}%  "
          f"{int(n_appr):>9,}  {pct_appr:>5.1f}%")
    summary.append(dict(leg=leg, tot=tot,
                        n_pres=int(n_pres), pct_pres=round(pct_pres, 1),
                        n_appr=int(n_appr), pct_appr=round(pct_appr, 1)))

# ── Breakdown per ramo ───────────────────────────────────────────────────────
print("\n── Copertura per ramo × legislatura (testo_presentato) ─────────────────")
print(f"{'Leg':>4}  {'Ramo':>6}  {'Tot':>7}  {'has_pres':>9}  {'%':>6}")
print("-" * 42)

for leg in range(13, 20):
    sub = df[df["legislatura"] == leg]
    for ramo in sorted(sub["ramo_origine"].dropna().unique()):
        s = sub[sub["ramo_origine"] == ramo]
        tot = len(s)
        n   = s["has_testo_presentato"].sum() if "has_testo_presentato" in s else 0
        pct = n / tot * 100 if tot else 0
        print(f"  {leg:>2}  {ramo:>6}  {tot:>7,}  {int(n):>9,}  {pct:>5.1f}%")

# ── Breakdown per progressivoIter ────────────────────────────────────────────
print("\n── Copertura per progressivoIter (prime fasi vs fasi successive) ───────")
print(f"{'Leg':>4}  {'progIter':>9}  {'Tot':>7}  {'has_pres':>9}  {'%':>6}")
print("-" * 46)

for leg in [17, 18]:                # solo due leg rappresentative
    sub = df[df["legislatura"] == leg]
    for pi in sorted(sub["progressivo_iter"].dropna().unique())[:4]:  # max 4 valori
        s = sub[sub["progressivo_iter"] == pi]
        tot = len(s)
        n   = s["has_testo_presentato"].sum() if "has_testo_presentato" in s else 0
        pct = n / tot * 100 if tot else 0
        print(f"  {leg:>2}  {int(pi):>9}  {tot:>7,}  {int(n):>9,}  {pct:>5.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# PARTE 2 — testoUnificato nel triplestore
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 2 — Copertura osr:testoUnificato nel triplestore (COUNT SPARQL)")
print("=" * 72)

unif_results = []

for leg in range(13, 20):
    print(f"\n── Leg{leg} ──────────────────────────────────────────────────────")

    # Count DDL con testoUnificato
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n)
WHERE {{ ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:testoUnificato ?val }}
""", f"COUNT testoUnificato Leg{leg}")
    n_unif = int(v(r[0], "n")) if r else -1

    # Count DDL con testoPresentato (verifica triplestore vs parquet)
    r2 = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n)
WHERE {{ ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:testoPresentato ?val }}
""", f"COUNT testoPresentato Leg{leg}")
    n_pres_ts = int(v(r2[0], "n")) if r2 else -1

    # Count DDL con testoApprovato (verifica triplestore vs parquet)
    r3 = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n)
WHERE {{ ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:testoApprovato ?val }}
""", f"COUNT testoApprovato Leg{leg}")
    n_appr_ts = int(v(r3[0], "n")) if r3 else -1

    # Totale DDL nel triplestore per confronto
    r4 = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?ddl) AS ?n)
WHERE {{ ?ddl a osr:Ddl ; osr:legislatura {leg} }}
""", f"COUNT totale Leg{leg}")
    n_tot_ts = int(v(r4[0], "n")) if r4 else -1

    pct_unif = n_unif / n_tot_ts * 100 if n_tot_ts > 0 and n_unif >= 0 else 0
    pct_pres = n_pres_ts / n_tot_ts * 100 if n_tot_ts > 0 and n_pres_ts >= 0 else 0
    pct_appr = n_appr_ts / n_tot_ts * 100 if n_tot_ts > 0 and n_appr_ts >= 0 else 0

    print(f"  Totale DDL triplestore   : {n_tot_ts:>8,}")
    print(f"  testoPresentato          : {n_pres_ts:>8,}  ({pct_pres:.1f}%)")
    print(f"  testoApprovato           : {n_appr_ts:>8,}  ({pct_appr:.1f}%)")
    print(f"  testoUnificato           : {n_unif:>8,}  ({pct_unif:.1f}%)")

    unif_results.append(dict(leg=leg, tot=n_tot_ts,
                             n_pres=n_pres_ts, pct_pres=round(pct_pres, 1),
                             n_appr=n_appr_ts, pct_appr=round(pct_appr, 1),
                             n_unif=n_unif, pct_unif=round(pct_unif, 1)))

    time.sleep(1.5)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 3 — Campione URN per capire il pattern URL
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 3 — Campione URN testi (pattern URL/URN)")
print("=" * 72)

for leg in [13, 16, 17, 19]:   # campione legislature diverse
    print(f"\n── Leg{leg} — campione testoPresentato ─────────────────────────────")
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?ddl ?ramo ?val
WHERE {{
  ?ddl a osr:Ddl ; osr:legislatura {leg} ;
       osr:testoPresentato ?val .
  OPTIONAL {{ ?ddl osr:ramo ?ramo }}
}}
LIMIT 6
""", f"campione testoPresentato Leg{leg}")
    if r:
        for row in r:
            ramo = v(row, "ramo") or "?"
            urn  = v(row, "val")
            print(f"  [{ramo}] {urn[:100]}")
    else:
        print("  (nessun risultato)")
    time.sleep(1)

    print(f"\n── Leg{leg} — campione testoUnificato ──────────────────────────────")
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?ddl ?val
WHERE {{
  ?ddl a osr:Ddl ; osr:legislatura {leg} ;
       osr:testoUnificato ?val .
}}
LIMIT 4
""", f"campione testoUnificato Leg{leg}")
    if r:
        for row in r:
            urn = v(row, "val")
            print(f"  {urn[:100]}")
    else:
        print("  (nessun testoUnificato in Leg{leg})")
    time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# RIEPILOGO FINALE
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("RIEPILOGO — Copertura testi DDL (triplestore)")
print("=" * 72)
print(f"{'Leg':>4}  {'Tot TS':>8}  {'Pres':>7}  {'%P':>5}  "
      f"{'Appr':>7}  {'%A':>5}  {'Unif':>7}  {'%U':>5}")
print("-" * 65)
for r in unif_results:
    print(f"  {r['leg']:>2}  {r['tot']:>8,}  {r['n_pres']:>7,}  {r['pct_pres']:>4.1f}%"
          f"  {r['n_appr']:>7,}  {r['pct_appr']:>4.1f}%"
          f"  {r['n_unif']:>7,}  {r['pct_unif']:>4.1f}%")

print()
print("Legenda:")
print("  Pres  = osr:testoPresentato (testo originale depositato)")
print("  Appr  = osr:testoApprovato  (testo votato/approvato in quella fase)")
print("  Unif  = osr:testoUnificato  (testo da fusione di più DDL)")
print()
print("INTERPRETAZIONE:")
print("  - Se %Pres << 100%: molti DDL non hanno testo presentato lato Senato")
print("    → probabile gap per ramo=C (testo sta sul lato Camera)")
print("  - Se %Unif significativo (>5%): la fusione DDL è un fenomeno rilevante")
print("    da includere come variabile nel dataset analitico")
print("  - Pattern URN: verificare se 'urn:nir:' o URL HTTP diretto")
print("    → determina la pipeline di download (NIRServer vs fetch diretto)")
