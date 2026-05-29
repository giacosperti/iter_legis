# Prompt T6 — fetch_emendamenti_camera.py

## Contesto operativo

Leggi prima questi file:
- `iter-legis/CLAUDE.md` — regole universali del progetto
- `iter-legis/claudesss/claude_T6.md` — specifiche tecniche di questo task
- `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/Ontologia_camera.md` — ontologia Camera

## Task

Scrivi `script_prova/fetch_emendamenti_camera.py` che scarica i bollettini HTML degli emendamenti Camera (Leg16–19).

## Struttura dati

Gli emendamenti Camera sono allegati collettivi (`ocd:allegatoDiscussione`) ai bollettini di seduta, NON entità individuali. La catena è:
```
ocd:atto → ocd:rif_dibattito → ocd:dibattito → ocd:rif_allegatoDiscussione
  → ocd:allegatoDiscussione → dc:relation → URL bollettino HTML
```

## Specifiche

1. Query SPARQL sull'endpoint Camera per ottenere URL bollettini per ogni atto
2. Scarica HTML bollettino (Referer obbligatorio)
3. Salva `data/raw/camera/emendamenti/leg{N}/{id_allegato}.html`
4. Salva `.meta.json`

## Header obbligatorio

```python
headers = {"Referer": "http://documenti.camera.it/", "User-Agent": "iter-legis-dataset/1.0"}
```

## URI legislatura Camera

```
http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}
```
NON `/legislatura/{N}` — causa 0 risultati.

## Note

- Leg13–15: 0 allegati (pre-digitale) — saltare
- Usare ALWAYS `SELECT DISTINCT` (triplestore Camera ha triple duplicate)
- Sleep 1s, retry 3×, idempotente
- Dipendenze: `beautifulsoup4`, `lxml`

## Output atteso finale

Descrivi il piano in 3 frasi, poi scrivi il codice. Attendi conferma esplicita di Giacomo prima di scrivere.
