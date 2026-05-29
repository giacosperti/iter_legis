# claude_T6.md — fetch_emendamenti_camera.py

## Obiettivo

Scaricare i testi degli emendamenti Camera (Leg16–19) tramite parsing HTML dei bollettini di seduta.

## Struttura dati Camera — emendamenti

Gli emendamenti Camera NON sono entità individuali nel triplestore. Sono **allegati collettivi** ai bollettini di seduta, class `ocd:allegatoDiscussione`.

Catena ontologica:
```
ocd:atto
  ← ocd:rif_attoCamera (su ocd:dibattito)
ocd:dibattito
  → ocd:rif_discussione → ocd:discussione
  → ocd:rif_allegatoDiscussione → ocd:allegatoDiscussione
    → dc:relation → URL bollettino HTML (~44 KB)
```

## Copertura per legislatura

| Leg | Totale allegati | Con emend | % |
|---|---|---|---|
| 13–15 | 0 | 0 | — (pre-digitale) |
| 16 | 989 | 291 | 29.4% |
| 17 | 11.841 | 1.575 | 13.3% |
| 18 | 9.044 | 1.001 | 11.1% |
| 19 | 7.030 | 912 | 13.0% |

## URL bollettino

```
https://documenti.camera.it/apps/commonServices/getDocumento.ashx?
  sezione=bollettini&tipoDoc=allegato&idLegislatura={N}&anno=...
  &idcommissione=...&pagina={ancora}&ancora={ancora}
```

Restituisce **HTML** (~44 KB), non PDF. Il parametro `ancora` identifica la sezione nel bollettino.

**Header obbligatorio**: `Referer: http://documenti.camera.it/` — senza → HTTP 403.

## Output

- `data/raw/camera/emendamenti/leg{N}/{id_allegato}.html` (bollettino HTML)
- `data/raw/camera/emendamenti/leg{N}/{id_allegato}.meta.json`

## Parsing HTML

Ogni bollettino contiene più sezioni di emendamenti. Usare BeautifulSoup per navigare all'`ancora` e estrarre il blocco HTML dell'emendamento specifico.

## Convenzioni

- Script in `script_prova/fetch_emendamenti_camera.py`
- CLI: `--legs`, `--force`, `--dry-run`
- Dipendenze aggiuntive: `beautifulsoup4`, `lxml`
- Sleep 1s tra download, retry 3×
- URI legislatura Camera: `http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}` (NON `/legislatura/{N}`)
