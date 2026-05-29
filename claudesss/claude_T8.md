# claude_T8.md — build_dataset_analitico.py

## Obiettivo

Assemblare tutte le tabelle prodotte nei task precedenti in un database DuckDB analitico.

## Input

| File | Task di produzione |
|---|---|
| `data/meta/atti_senato.parquet` | T1 + T1v2 |
| `data/meta/atti_camera.parquet` | T2 |
| `data/meta/atti_senato_firmatari.parquet` | T1v2 |
| `data/meta/t_votazioni.parquet` | T7b |
| `data/meta/t_fasi_iter.parquet` | T7a |
| `data/coalizioni_leg13_19.csv` | T-Coal |

## Output

`data/dataset/iter_legis.duckdb` con le seguenti tabelle:

```
t_atti_senato       — metadati DDL Senato + firmatari aggregati
t_atti_camera       — metadati DDL Camera + firmatari aggregati
t_firmatari_senato  — dettaglio firmatari × DDL × senatore × gruppo
t_votazioni         — risultati votazioni per senatore
t_fasi_iter         — timeline iter
t_coalizioni        — maggioranza/opposizione per legislatura × gruppo
```

## Join chiave

```sql
-- DDL Senato × firmatari × gruppo parlamentare
t_atti_senato
  JOIN t_firmatari_senato ON id_fase
  JOIN t_coalizioni ON (legislatura, gruppo_uri)

-- Colonne derivate da calcolare
giorni_iter    = data_stato_ddl - data_presentazione
n_gruppi_firmatari = COUNT(DISTINCT gruppo_uri) per id_fase
pct_emend_maggioranza = ...
```

## Colonne calcolate da aggiungere

- `giorni_iter`: giorni dalla presentazione all'ultimo stato iter
- `n_firmatari`: numero di firmatari per DDL
- `n_gruppi_firmatari`: numero di gruppi parlamentari distinti tra i firmatari
- `is_governativo`: True se `natura` contiene "DL" o `descr_iniziativa` = "Governativa"
- `n_emendamenti_per_leg`: aggregato per legislatura

## Convenzioni

- Script in `script_prova/build_dataset_analitico.py`
- Il DB DuckDB viene creato da zero ad ogni run (no append incrementale)
- Flag `--validate`: stampa statistiche di copertura per ogni tabella
- Scrittura sempre via DuckDB — nessun Parquet intermedio in questo script
