# Prompt T5 — fetch_emendamenti_senato.py

## Contesto operativo

Leggi prima questi file:
- `iter-legis/CLAUDE.md` — regole universali del progetto
- `iter-legis/claudesss/claude_T5.md` — specifiche tecniche di questo task
- `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/ontologia_senato.md` — ontologia Senato

## Task

Scrivi `script_prova/fetch_emendamenti_senato.py` che scarica i file AKN degli emendamenti Senato.

## Specifiche

1. Leggi `data/meta/atti_senato.parquet`, filtra `has_emendamenti_akn == True`
2. Per ogni DDL: query SPARQL per lista emendamenti con `osr:URLTestoXml`
3. Scarica ogni file AKN → `data/raw/senato/{id_fase}/emendamenti/{id_emend}.akn.xml`
4. Salva `.meta.json` accanto
5. Log in `data/meta/fetch_log_emendamenti_senato.json`

## Catena SPARQL emendamenti

```
osr:Emendamento → osr:oggetto → osr:OggettoTrattazione → osr:relativoA → osr:Ddl
```
NON esiste link diretto osr:Emendamento → osr:Ddl.

## Encoding detection — CRITICO

Usare `chardet` per rilevare l'encoding prima del parsing:
- Leg14: UTF-8 con BOM
- Leg18: UTF-16 LE  
- Leg19: ISO-8859-1

## Emendamenti orfani

~6–9% degli emendamenti ha catena `osr:oggetto → osr:relativoA` spezzata. Non recuperabili. Non trattarli come errori — loggarli come `skipped_orphan`.

## Regole obbligatorie

- Idempotente, sleep 0.5s, retry 3×
- `--legs`, `--force`, `--dry-run`, `--limit-ddl`
- DuckDB COPY TO per Parquet
- Dipendenza aggiuntiva: `chardet`
- Commenti in inglese

## Output atteso finale

Descrivi il piano in 3 frasi, poi scrivi il codice. Attendi conferma esplicita di Giacomo prima di scrivere.
