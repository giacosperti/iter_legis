# claude_T4.md — fetch_testi_presentati_camera.py

## Obiettivo

Scaricare i PDF dei testi presentati per i DDL Camera (Leg16–19) e DDL Senato con `ramo_origine = 'C'`.

## Input

`data/meta/atti_camera.parquet` — colonna `url_testo_presentato` (già disponibile per Leg16–19)
`data/meta/atti_senato.parquet` — filtrare `ramo_origine == 'C'` (testo su Camera)

## Output

- `data/raw/camera/{id_atto}/testo_presentato.pdf`
- `data/raw/camera/{id_atto}/testo_presentato.pdf.meta.json`
- `data/meta/fetch_log_testi_camera.json`

## Pipeline testi Camera

### Leg16–19 (via `ocd:rif_versioneTestoAtto`)

`url_testo_presentato` nel parquet Camera punta a `getDocumento.ashx`:
```
https://documenti.camera.it/apps/commonServices/getDocumento.ashx?...
```
Richiede header obbligatorio: `Referer: http://documenti.camera.it/`

### Leg13–15 (via `dc:relation` diretto)

Per le legislature pre-digitali `ocd:rif_versioneTestoAtto` ha copertura 0% — usare `dc:relation` sull'atto:
```
http://www.camera.it/_dati/leg{N}/lavori/stampati/pdf/{NNNN}.pdf
```
Formato URL: codice a 4 cifre zero-padded (diverso dal formato Leg17+ `{N}PDL{code}.pdf`).

## Note tecniche critiche

- **Sempre** aggiungere `Referer: http://documenti.camera.it/` — senza header → HTTP 403
- Dominio varia: Leg13–17 `www.camera.it`, Leg18–19 `documenti.camera.it`
- Leg13–15: `ocd:rif_versioneTestoAtto` = 0% → usare fallback `dc:relation`
- Leg16: `ocd:rif_statoIter` = 0.3% genuino — non è artefatto
- `dc:type == "Relazione"` in Leg13–14 (~10%): filtrare, non sono PDL

## Convenzioni

- Script in `script_prova/fetch_testi_presentati_camera.py`
- CLI: `--legs`, `--force`, `--dry-run`, `--limit`
- Sleep 1–2s tra download, retry 3×, idempotenza
- sha256 + `.meta.json` per ogni file
