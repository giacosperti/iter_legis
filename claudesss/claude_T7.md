# claude_T7.md — Tabelle temporali: t_fasi_iter e t_votazioni

## Obiettivo

Estrarre dal triplestore Senato:
1. Timeline fasi iter per DDL (`t_fasi_iter`)
2. Risultati votazioni per senatore con data (`t_votazioni`)

## T7a — `t_fasi_iter` (via osr:IterDdl)

### Struttura osr:IterDdl

- 53.745 istanze totali nel triplestore
- `osr:idDdl` (integer) — collega al DDL (join possibile con `id_ddl_interno` da atti_senato.parquet)
- `osr:fase` → punta a **blank nodes** (NON a DDL navigabili): NON usare per navigazione
- `osr:assorbimento`, `osr:testoUnificato`, `osr:stralcio` — flag
- NON ha `osr:legislatura` — filtrare via join con DDL: `?ddl osr:idDdl ?id . ?ddl osr:legislatura ?leg`

### osr:FaseIter — NON usare

Query GROUP BY su `osr:FaseIter` restituiscono HTTP 400. La classe ha solo `osr:relativoA` e `osr:progrIter` — nessuna proprietà data. COUNT = 0 su Leg13–19. **Non usare questa classe.**

## T7b — `t_votazioni` (via osr:Votazione)

### Struttura osr:Votazione

- Dati per singolo senatore: favorevole/contrario/astenuto/presente
- `osr:esito`, link a `osr:seduta`, conteggi presenti/votanti/maggioranza

### Path per la data di votazione

`osr:seduta` è domain di `osr:Votazione | osr:Intervento` — NON di `osr:Emendamento`.

```sparql
?votazione a osr:Votazione ;
            osr:seduta ?seduta .
?seduta a osr:SedutaAssemblea ;
        osr:dataSeduta ?data .
```

### Path per la data degli emendamenti

```sparql
# Emendamento non ha osr:seduta direttamente.
# Path: Emendamento → OggettoTrattazione ← oggetto ← Votazione → seduta → data
?vot osr:oggetto ?ogg .
?emend osr:oggetto ?ogg .
?vot osr:seduta ?sed .
?sed osr:dataSeduta ?data .
```

## Output previsto

| Tabella | Chiave | Colonne principali |
|---|---|---|
| `t_fasi_iter` | `id_iter` | `id_ddl`, `legislatura`, `tipo_fase`, `data_fase`, `esito` |
| `t_votazioni` | `id_votazione` | `id_ddl`, `id_senatore`, `voto`, `data`, `esito_finale`, `presenti`, `votanti` |

## Nota su HTTP 400

Query GROUP BY su `osr:FaseIter` e `osr:SedutaCommissione` restituiscono HTTP 400 dall'endpoint Senato. Usare query senza HAVING; esplorare con dump di proprietà su campioni.

## Convenzioni

- Script in `script_prova/build_tabelle_temporali.py`
- Output in `data/meta/` come Parquet via DuckDB COPY TO
- Dipendenze: `duckdb`, `pandas`, `requests`
