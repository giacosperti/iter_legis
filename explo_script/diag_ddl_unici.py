#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "pyarrow"]
# ///
"""
diag_ddl_unici.py — Verifica quanti DDL unici ci sono per legislatura
e diagnostica la struttura di atti_senato.parquet.

Risponde a tre domande:
  1. Righe totali vs DDL unici (id_ddl_interno) per legislatura
     → capisce se i 10.000+ di Leg13/14 sono fasi multiple dello stesso DDL
  2. Distribuzione di progressivoIter
     → quanti DDL hanno 1, 2, 3+ passaggi inter-camerali
  3. Null rate di id_fase_sparql (colonna osr:idFase)
     → verifica che osr:idFase non esista come proprietà SPARQL esplicita
  4. Presenza di osr:testoApprovato nel dataset (colonna mancante)
     → campo esistente nell'ontologia ma non fetchato

Usage:
  uv run explo_script/diag_ddl_unici.py
  uv run explo_script/diag_ddl_unici.py --parquet data/meta/atti_senato.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Argomenti
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Diagnostica DDL unici nel parquet Senato")
parser.add_argument(
    "--parquet",
    type=Path,
    default=Path("data/meta/atti_senato.parquet"),
    help="Percorso del file atti_senato.parquet (default: data/meta/atti_senato.parquet)",
)
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Caricamento
# ---------------------------------------------------------------------------

if not args.parquet.exists():
    # fallback CSV
    csv_path = args.parquet.with_suffix(".csv")
    if csv_path.exists():
        print(f"⚠️  Parquet non trovato, carico CSV: {csv_path}")
        df = pd.read_csv(csv_path, dtype=str)
    else:
        print(f"❌ File non trovato: {args.parquet} (né la versione .csv)")
        raise SystemExit(1)
else:
    df = pd.read_parquet(args.parquet)

print(f"✅ Caricato: {args.parquet}  —  {len(df)} righe, {df['legislatura'].nunique()} legislature")
print(f"   Colonne: {list(df.columns)}")
print()

# ---------------------------------------------------------------------------
# 1. Righe totali vs DDL unici per legislatura
# ---------------------------------------------------------------------------

print("=" * 70)
print("1. Righe totali vs DDL unici per legislatura")
print("=" * 70)

# Convertiamo progressivoIter a numerico per le aggregazioni
df["progressivo_iter_num"] = pd.to_numeric(df["progressivo_iter"], errors="coerce")

summary = (
    df.groupby("legislatura")
    .agg(
        righe_totali       = ("id_fase",         "count"),
        ddl_unici_idddl    = ("id_ddl_interno",  "nunique"),
        prime_fasi         = ("is_prima_fase",    "sum"),
        ramo_S             = ("ramo_origine",     lambda x: (x == "S").sum()),
        ramo_C             = ("ramo_origine",     lambda x: (x == "C").sum()),
        has_testo_pres     = ("has_testo_presentato", "sum"),
        has_emend          = ("has_emendamenti",  "sum"),
    )
    .reset_index()
)

summary["fasi_per_ddl"] = (summary["righe_totali"] / summary["ddl_unici_idddl"]).round(2)
summary["pct_multifase"] = (
    (summary["righe_totali"] - summary["prime_fasi"]) / summary["righe_totali"] * 100
).round(1)

print(summary.to_string(index=False))
print()
print("Legenda:")
print("  righe_totali    = record totali nel parquet (una per fase)")
print("  ddl_unici_idddl = DDL unici per idDdl (disegni di legge distinti)")
print("  prime_fasi      = righe con progressivoIter=1 (presentazione originale)")
print("  fasi_per_ddl    = rapporto righe/DDL unici (>1 = DDL con passaggi multipli)")
print("  pct_multifase   = % di righe che sono passaggi successivi (non prima fase)")
print()

# ---------------------------------------------------------------------------
# 2. Distribuzione di progressivoIter per legislatura
# ---------------------------------------------------------------------------

print("=" * 70)
print("2. Distribuzione di progressivoIter (quanti passaggi ha un DDL?)")
print("=" * 70)

pivot = (
    df.groupby(["legislatura", "progressivo_iter_num"])
    .size()
    .unstack(fill_value=0)
    .rename(columns=lambda c: f"iter={int(c)}" if pd.notna(c) else "iter=NaN")
)
print(pivot.to_string())
print()

# ---------------------------------------------------------------------------
# 3. Null rate di id_fase_sparql (verifica osr:idFase)
# ---------------------------------------------------------------------------

print("=" * 70)
print("3. Null rate di id_fase_sparql — osr:idFase esiste come proprietà SPARQL?")
print("=" * 70)

if "id_fase_sparql" in df.columns:
    null_count = df["id_fase_sparql"].isna().sum()
    total      = len(df)
    null_pct   = null_count / total * 100
    print(f"  Valori nulli : {null_count} / {total}  ({null_pct:.1f}%)")
    if null_pct == 100:
        print("  ⚠️  osr:idFase restituisce SEMPRE null — la proprietà non esiste nel triplestore.")
        print("      L'ID di fase va estratto dall'URI (ultimo segmento), non da osr:idFase.")
    elif null_pct > 50:
        print("  ⚠️  osr:idFase è quasi sempre null — disponibile solo per alcune legislature.")
    else:
        print("  ✅ osr:idFase è popolata — la proprietà esiste nel triplestore.")

    # Confronto con id_fase (estratto dall'URI)
    if "id_fase" in df.columns:
        coincidono = (df["id_fase"] == df["id_fase_sparql"]).sum()
        print(f"\n  Coincidenza id_fase (URI) == id_fase_sparql: {coincidono} / {total}")
else:
    print("  ⚠️  Colonna id_fase_sparql non presente nel parquet.")
print()

# ---------------------------------------------------------------------------
# 4. Presenza osr:testoApprovato (proprietà nell'ontologia, non fetchata)
# ---------------------------------------------------------------------------

print("=" * 70)
print("4. osr:testoApprovato — colonna presente nel parquet?")
print("=" * 70)

if "urn_testo_approvato" in df.columns or "testo_approvato" in df.columns:
    col = "urn_testo_approvato" if "urn_testo_approvato" in df.columns else "testo_approvato"
    n_populated = df[col].notna().sum()
    print(f"  ✅ Colonna '{col}' trovata — {n_populated} valori non null")
else:
    print("  ❌ osr:testoApprovato NON è stata fetchata (colonna assente).")
    print("     È nell'ontologia ufficiale: va aggiunta alla query DDL_QUERY in")
    print("     fetch_metadati_senato.py come OPTIONAL { ?ddl osr:testoApprovato ?testo_approvato }")
print()

# ---------------------------------------------------------------------------
# 5. Campione di DDL multi-fase (progressivoIter > 1)
# ---------------------------------------------------------------------------

print("=" * 70)
print("5. Campione DDL con più fasi (navette inter-camerali)")
print("=" * 70)

multifase = df[df["progressivo_iter_num"] > 1].copy()
if multifase.empty:
    print("  Nessun DDL con progressivoIter > 1 trovato.")
else:
    # Gruppi con più fasi
    ddl_ids = multifase["id_ddl_interno"].dropna().unique()[:5]
    for ddl_id in ddl_ids:
        fasi = df[df["id_ddl_interno"] == ddl_id].sort_values("progressivo_iter_num")
        print(f"\n  idDdl={ddl_id}  ({len(fasi)} fasi)")
        for _, row in fasi.iterrows():
            print(
                f"    iter={row.get('progressivo_iter','')}  "
                f"fase={row.get('fase','')}  "
                f"ramo={row.get('ramo_origine','')}  "
                f"data={row.get('data_presentazione','')[:10] if pd.notna(row.get('data_presentazione','')) else ''}  "
                f"stato={str(row.get('stato_ddl',''))[:30]}"
            )

print()
print("=" * 70)
print("Diagnostica completata.")
print()
print("AZIONI SUGGERITE IN BASE AI RISULTATI:")
print("  - Se null_rate(id_fase_sparql) = 100% → rimuovere osr:idFase dalla query DDL_QUERY")
print("    e aggiornare §4.1 CLAUDE.md (osr:idFase non esiste come proprietà)")
print("  - Se fasi_per_ddl >> 1 per Leg13/14 → i 10.000+ sono corretti (navette multiple)")
print("    e per analisi su DDL unici filtrare su is_prima_fase=True")
print("  - osr:testoApprovato → se mancante, aggiungere alla query e al fetch")
