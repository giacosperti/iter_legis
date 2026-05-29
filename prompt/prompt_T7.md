# Prompt T7 — build_tabelle_temporali.py

## Contesto operativo

Leggi prima questi file:
- `iter-legis/CLAUDE.md` — regole universali del progetto
- `iter-legis/claudesss/claude_T7.md` — specifiche tecniche di questo task
- `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/ontologia_senato.md` — ontologia Senato

## Task

Scrivi `script_prova/build_tabelle_temporali.py` che estrae:
1. `t_votazioni`: risultati votazioni Senato per senatore con data
2. `t_fasi_iter`: timeline iter via `osr:IterDdl`

## Specifiche votazioni

```sparql
PREFIX osr: <http://dati.senato.it/osr/>

SELECT ?vot ?ddl ?seduta ?data WHERE {
  ?vot a osr:Votazione ;
       osr:oggetto ?ogg ;
       osr:seduta  ?seduta .
  ?ogg osr:relativoA ?ddl .
  ?seduta osr:dataSeduta ?data .
  ?ddl osr:legislatura {leg} .
}
```

## Specifiche fasi iter

`osr:IterDdl` join con DDL via `osr:idDdl` (NON via `osr:fase` che punta a blank node):
```sparql
?iter a osr:IterDdl ; osr:idDdl ?id_ddl .
?ddl osr:idDdl ?id_ddl ; osr:legislatura {leg} .
```

## Attenzioni critiche

- `osr:FaseIter`: NON usare — query GROUP BY → HTTP 400, COUNT = 0 su tutte le legislature
- `osr:seduta` ha domain SOLO `osr:Votazione | osr:Intervento` — NON su Emendamento
- `osr:IterDdl → osr:fase` → blank node (NON navigabile come URI)
- Usare Leg17/18 per i test (legislature complete e terminate)

## Output

- `data/meta/t_votazioni.parquet`
- `data/meta/t_fasi_iter.parquet`

## Regole obbligatorie

- Keyset pagination (cap endpoint Virtuoso)
- DuckDB COPY TO per Parquet
- `--legs`, `--force`, `--dry-run`
- Commenti in inglese

## Output atteso finale

Descrivi il piano in 3 frasi, poi scrivi il codice. Attendi conferma esplicita di Giacomo prima di scrivere.
