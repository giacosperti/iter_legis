# Prompt T4 — fetch_testi_presentati_camera.py

## Contesto operativo

Leggi prima questi file:
- `iter-legis/CLAUDE.md` — regole universali del progetto
- `iter-legis/claudesss/claude_T4.md` — specifiche tecniche di questo task
- `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/Ontologia_camera.md` — ontologia Camera

## Task

Scrivi lo script `script_prova/fetch_testi_presentati_camera.py` che scarica i PDF dei testi presentati dai DDL Camera.

## Specifiche

1. **Leg16–19**: leggi `data/meta/atti_camera.parquet`, colonna `url_testo_presentato`
2. **Leg13–15**: usa `dc:relation` sull'atto (URL PDF diretto) — `ocd:rif_versioneTestoAtto` ha copertura 0%
3. Salva `data/raw/camera/{id_atto}/testo_presentato.pdf`
4. Salva `.meta.json` con: `{fonte, url, size_bytes, sha256, data_fetch, legislatura}`
5. Log riepilogativo in `data/meta/fetch_log_testi_camera.json`

## Header obbligatorio

```python
headers = {
    "Referer": "http://documenti.camera.it/",
    "User-Agent": "iter-legis-dataset/1.0",
}
```
Senza `Referer` → HTTP 403.

## Distinzione per legislatura

| Leg | Pipeline | Dominio |
|---|---|---|
| 13–15 | `dc:relation` diretto (URL PDF grezzo) | `www.camera.it` |
| 16–19 | `url_testo_presentato` dal parquet | `documenti.camera.it` |

## Regole obbligatorie (da CLAUDE.md)

- Idempotente, sleep 1.5s, retry 3×
- `--dry-run`, `--force`, `--legs`, `--limit`
- DuckDB COPY TO per qualsiasi Parquet
- Commenti in inglese
- NON modificare `script/`, script in `script_prova/`

## Output atteso finale

Descrivi il piano in 3 frasi, poi scrivi il codice. Attendi conferma esplicita di Giacomo prima di scrivere.
