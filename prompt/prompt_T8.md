# Prompt T8 — build_dataset_analitico.py

## Contesto operativo

Leggi prima questi file:
- `iter-legis/CLAUDE.md` — regole universali del progetto
- `iter-legis/claudesss/claude_T8.md` — specifiche tecniche di questo task
- `iter-legis/readme_datasetbuilding.md` — schema completo colonne e architettura dati

## Prerequisiti

Prima di eseguire questo task devono essere completati: T1v2, T2, T3 (o T4), T7.
File attesi in input: `atti_senato_v2.parquet`, `atti_camera.parquet`, `firmatari_senato.parquet`, `t_votazioni.parquet`, `t_fasi_iter.parquet`, `coalizioni_leg13_19.csv`.

## Task

Scrivi `script_prova/build_dataset_analitico.py` che assembla tutte le tabelle in `data/dataset/iter_legis.duckdb`.

## Specifiche

Il database DuckDB contiene:
- `t_atti_senato` — da `atti_senato_v2.parquet`
- `t_atti_camera` — da `atti_camera.parquet`
- `t_firmatari_senato` — da `firmatari_senato.parquet`
- `t_votazioni` — da `t_votazioni.parquet`
- `t_fasi_iter` — da `t_fasi_iter.parquet`
- `t_coalizioni` — da `coalizioni_leg13_19.csv`

## Colonne derivate da calcolare in DuckDB SQL

```sql
ALTER TABLE t_atti_senato ADD COLUMN giorni_iter INTEGER AS (
  DATEDIFF('day', data_presentazione::DATE, data_stato_ddl::DATE)
);
```

## Validazione

Con `--validate`: stampa COUNT(*) per ogni tabella + statistiche di copertura chiave.

## Regole obbligatorie

- Il DB viene ricreato da zero ad ogni run (no append — garantisce riproducibilità)
- `--validate`, `--force`, `--dry-run`
- Commenti in inglese

## Output atteso finale

Descrivi il piano in 3 frasi, poi scrivi il codice. Attendi conferma esplicita di Giacomo prima di scrivere.
