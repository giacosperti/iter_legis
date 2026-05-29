# Prompt T9 — build_complessita_testuale.py

## Contesto operativo

Leggi prima questi file:
- `iter-legis/CLAUDE.md` — regole universali del progetto
- `iter-legis/claudesss/claude_T9.md` — specifiche tecniche di questo task

## Prerequisiti

T3 e T4 completati (PDF scaricati). T5 completato (file AKN disponibili).

## Task

Questo task richiede allineamento preliminare con Giacomo sulle misure di complessità da calcolare prima di scrivere codice. Le misure candidate sono documentate in `claudesss/claude_T9.md`.

Proponi a Giacomo:
1. Quali misure calcolare per prima (Gulpease, lunghezza, riferimenti normativi)
2. Se usare NLP italiano (spacy `it_core_news_lg`) o approccio più semplice (regex + conteggi)
3. Come gestire PDF scansionati (OCR con pytesseract o saltare)
4. Formato output: un Parquet per atto + colonna per misura

Solo dopo l'allineamento: scrivi `script_prova/build_complessita_testuale.py`.

## Regole obbligatorie

- Elaborazione in batch con checkpoint ogni 500 atti
- Idempotente: skip se id_atto già presente nell'output
- DuckDB COPY TO per Parquet
- Commenti in inglese

## Output atteso finale

Prima di scrivere codice: proponi le scelte di cui sopra e attendi conferma esplicita di Giacomo.
