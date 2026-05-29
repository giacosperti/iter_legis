# Prompt T3 — fetch_testi_presentati_senato.py

## Contesto operativo

Leggi prima questi file:
- `iter-legis/CLAUDE.md` — regole universali del progetto
- `iter-legis/claudesss/claude_T3.md` — specifiche tecniche di questo task
- `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/ontologia_senato.md` — ontologia Senato

## Task

Scrivi lo script `script_prova/fetch_testi_presentati_senato.py` che scarica i PDF dei testi presentati dei DDL Senato.

## Specifiche

1. Leggi `data/meta/atti_senato.parquet`
2. Filtra: `has_testo_presentato == True AND is_prima_fase == True AND ramo_origine == 'S'`
3. Per ogni riga: risolvi il NIR URN in URL PDF e scarica
4. Salva `data/raw/senato/{id_fase}/testo_presentato.pdf`
5. Salva `.meta.json` accanto al PDF con: `{fonte, urn, url_effettivo, size_bytes, sha256, data_fetch}`
6. Salva log riepilogativo in `data/meta/fetch_log_testi_senato.json`

## Pipeline NIR URN

```
urn:nir:senato.repubblica:disegno.legge:N.legislatura;numero
  → GET https://www.senato.it/uri-res/N2Ls?{urn_encoded}
  → HTML → estrai link PDF (pattern: /service/PDF/PDFServer/BGT/)
  → GET pdf_url → salva bytes
```

**Importante**: `osr:testoPresentato` contiene NIR URN per tutte le legislature Leg13–19 (confermato empiricamente 2026-05-29). NON contiene URL diretti AKN XML per Leg17–19 — la pipeline PDF via N2Ls è l'unica pipeline corretta.

## Regole obbligatorie (da CLAUDE.md)

- Idempotente: skip se PDF già esiste
- Sleep 1.5s tra download
- Retry 3× con 5s di attesa
- `--dry-run`, `--force`, `--legs`, `--limit` come CLI args
- DuckDB COPY TO per qualsiasi output Parquet
- Commenti in inglese, citare le scoperte diagnostiche con data ISO 8601
- `uv run` con `# /// script` header
- NON modificare `script/`
- Script in `script_prova/`, non in `explo_script/`

## Output atteso finale

Descrivi il piano in 3 frasi, poi scrivi il codice. Attendi conferma esplicita di Giacomo prima di scrivere.
