# claude_T9.md — Misure di complessità testuale

## Obiettivo

Calcolare indici di complessità testuale sui PDF dei testi presentati e degli emendamenti.

## Input

- `data/raw/senato/{id_fase}/testo_presentato.pdf` (da T3)
- `data/raw/camera/{id_atto}/testo_presentato.pdf` (da T4)
- `data/raw/senato/{id_fase}/emendamenti/{id_emend}.akn.xml` (da T5)

## Output

`data/meta/complessita_testuale.parquet` con colonne:

| Colonna | Descrizione |
|---|---|
| `id_atto` | ID fase (Senato) o ID atto (Camera) |
| `fonte` | "senato" / "camera" |
| `n_caratteri` | Lunghezza testo grezzo |
| `n_parole` | Conteggio parole |
| `n_frasi` | Conteggio frasi |
| `n_articoli` | Numero articoli del DDL |
| `n_commi` | Numero totale commi |
| `gulpease` | Indice di leggibilità Gulpease |
| `n_riferimenti_normativi` | Conteggio cross-references a leggi citate |
| `lunghezza_media_articolo` | Caratteri / articolo |

## Misure previste

### Indice Gulpease

Formula italiana:
```
G = 89 - (10 × n_lettere/n_parole) + (300 × n_frasi/n_parole)
```
Valori: 0–100 (più basso = più complesso). Soglie: <40 incomprensibile, 40–60 difficile, 60–80 normale, >80 semplice.

### Riferimenti normativi

Contare pattern regex del tipo:
- `legge \d+ del \d{4}`
- `decreto legislativo \d+/\d{4}`
- `art\. \d+`
- `d\.l\. \d+`

### Estrazione testo PDF

Usare `pdfminer.six` o `pypdf` (NON il pdf skill). Fallback OCR con `pytesseract` per PDF scansionati.

## Nota operativa

Questo task è definito in linea di massima — i dettagli sulle misure da calcolare e sui soglie di leggibilità vanno concordati con Giacomo prima dell'implementazione.

## Convenzioni

- Script in `script_prova/build_complessita_testuale.py`
- Dipendenze: `pdfminer.six`, `pypdf`, `nltk` o `spacy`
- Elaborazione in batch, checkpoint ogni 500 atti
- Idempotente: skip se id_atto già nel parquet di output
