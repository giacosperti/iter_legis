# claude_T3.md — fetch_testi_presentati_senato.py

## Obiettivo

Scaricare i PDF dei testi presentati per tutti i DDL Senato con `ramo_origine = 'S'` e `is_prima_fase = True`.

## Input

`data/meta/atti_senato.parquet` — filtrare: `has_testo_presentato == True AND is_prima_fase == True AND ramo_origine == 'S'`

## Output

- `data/raw/senato/{id_fase}/testo_presentato.pdf`
- `data/raw/senato/{id_fase}/testo_presentato.pdf.meta.json` (fonte, data_fetch, urn, url_effettivo, size_bytes, sha256)
- `data/meta/fetch_log_testi_senato.json` (log riepilogativo)

## Pipeline NIR URN Senato (confermata uniforme Leg13–19)

```
urn:nir:senato.repubblica:disegno.legge:{N}.legislatura;{numero}
    → GET https://www.senato.it/uri-res/N2Ls?{urn}
    → pagina HTML con link PDF
    → PDF: https://www.senato.it/service/PDF/PDFServer/BGT/{id}.pdf
```

Il prefisso è `urn:nir:` (NON `urn:lex:it:`). Il numero può contenere lettere (es. `813-B`).
La risoluzione URN è uniforme per tutte le legislature — nessuna differenza Leg13-16 vs Leg17-19.

**Nota critica**: `osr:testoPresentato` contiene NIR URN per tutte le legislature (Leg13–19), confermato empiricamente 2026-05-29 leggendo `atti_senato_v2.parquet`. NON contiene URL diretti AKN XML per nessuna legislatura — l'unica pipeline corretta è PDF via N2Ls.

## Nota: testo approvato definitivamente

Fuori scope di questo task. `osr:testoApprovato` esiste nel triplestore (NIR URN con segmento `;approvato`, es. `urn:nir:senato.repubblica:disegno.legge;approvato:19.legislatura;998`) ma copertura solo 2.6–7.9% — solo DDL effettivamente convertiti in legge. Per testo approvato sistematico: normattiva (task separato, fuori scope T3–T9).

## Regole tecniche

- Rate limiting: sleep 1–2 secondi tra download
- Retry: 3 tentativi con 5 secondi di attesa
- Idempotenza: skip se PDF già esiste (controlla `data/raw/senato/{id_fase}/testo_presentato.pdf`)
- Header HTTP da usare: `User-Agent: iter-legis-dataset/1.0`
- Salvare sha256 del PDF per integrità

## Convenzioni

- Script in `script_prova/fetch_testi_presentati_senato.py`
- CLI: `--legs`, `--force`, `--dry-run`, `--limit` (per test)
- `uv run` con `# /// script` header
- Logging strutturato in JSON
- Commenti in inglese (vedi §12/§13 CLAUDE.md)
- Scrittura Parquet solo via DuckDB COPY TO
