# CLAUDE.md — iter-legis

Regole universali applicabili a **tutte** le task del progetto.
Per dettagli tecnici specifici per task: `claudesss/claude_T{N}.md`
Per schema dati, bug noti, fatti triplestore: `readme_datasetbuilding.md`
Per prompt pronti all'esecuzione: `prompt/prompt_T{N}.md`

---

## 0. Protocollo di auto-aggiornamento

Aggiornare CLAUDE.md **solo** se il fatto da documentare è universale (vale per tutte le task).
Fatti specifici per task → `claudesss/claude_T{N}.md`.
Fatti tecnici sul triplestore → `readme_datasetbuilding.md`.

**Prima di modificare qualsiasi file .md è obbligatorio ottenere conferma esplicita di Giacomo.**

Flusso:
1. Identificare il fatto nuovo e il file pertinente
2. Descrivere sinteticamente la modifica proposta
3. Attendere conferma ("sì", "procedi", "ok")
4. Modificare in modo chirurgico
5. Aggiungere riga al Registro revisioni del file modificato

### Registro revisioni

| Data | File modificato | Motivo |
|---|---|---|
| 2026-05-27 | CLAUDE.md | Prima stesura completa |
| 2026-05-28 | CLAUDE.md | Aggiunte §4.7–§4.9, §9.2, §10 aggiornato |
| 2026-05-29 | CLAUDE.md + readme_datasetbuilding.md + claudesss/ + prompt/ | Ristrutturazione: fatti tecnici → readme, task-specifici → claudesss/, CLAUDE.md ridotto a regole universali |

---

## 1. Contesto di tesi

**Obiettivo**: analizzare la relazione tra frammentazione politica e complessità legislativa in Italia, legislature 13–19 (1996–oggi).

**Endpoint SPARQL**:
- Senato: `https://dati.senato.it/sparql` — prefisso `osr: <http://dati.senato.it/osr/>`
- Camera: `https://dati.camera.it/sparql` — prefisso `ocd: <http://dati.camera.it/ocd/>`

**Ontologie di riferimento** — leggere prima di scrivere qualsiasi query SPARQL:
- Senato: `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/ontologia_senato.md`
- Camera: `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/Ontologia_camera.md`

L'ontologia Senato è il file .ttl ufficiale. L'ontologia Camera è il file OWL ufficiale in XML/RDF.

---

## 2. Regole obbligatorie — valgono per TUTTE le task

1. **Non modificare mai `script/`**. Quella cartella contiene gli script originali del collaboratore. Per versioni sperimentali usare `script_prova/` con nomi distinguibili.
2. **Script esplorativi/diagnostici in `explo_script/`**, mai in `script_prova/`.
3. **Prima di produrre codice, descrivere sempre il piano** e attendere conferma esplicita di Giacomo.
4. **Lavorare per task chiuse**: apri un problema, risolvilo, verifica, chiudi, poi passa al prossimo.
5. **Usare Leg17 o Leg18 per i test** (legislature complete e terminate).
6. **Ogni script deve essere idempotente**: controlla esistenza output prima di rieseguire.
7. **Nessun secret o credenziale** nel codice.
8. **Tutti gli script usano `uv run`** con `# /// script` header per le dipendenze inline.
9. **Prima di scrivere query SPARQL**, leggere l'ontologia pertinente (§1). Non inventare nomi di proprietà.
10. **Scrittura Parquet**: usare sempre DuckDB `COPY TO`. Mai `pandas.to_parquet()` — produce formato 2.6 incompatibile con pyarrow < 24.

---

## 3. Struttura cartelle

```
iter-legis/
├── script/             # ⛔ INTOCCABILE — script originali collaboratore
├── script_prova/       # Script di produzione nuovi
│   ├── fetch_metadati_senato.py       ✅ T1 completato
│   ├── fetch_metadati_camera.py       ✅ T2 completato
│   ├── fetch_anagrafica_sparql.py     ✅ completato
│   └── build_coalizioni.py            ✅ completato
├── explo_script/       # Script diagnostici (usa e getta)
├── claudesss/          # Guide operative task-specifiche
│   ├── claude_T3.md … claude_T9.md
│   ├── claude_T_senato_v2.md
│   └── claude_T_camera_v2.md
├── prompt/             # Prompt self-contained per Claude Code
│   ├── prompt_T3.md … prompt_T9.md
│   ├── prompt_fetch_senato_v2.md
│   └── prompt_fetch_camera_v2.md
├── data/
│   ├── raw/            # PDF, AKN, HTML scaricati
│   ├── meta/           # Parquet/CSV metadati strutturati
│   ├── text/           # Testo estratto .txt
│   └── dataset/        # iter_legis.duckdb (dataset finale)
├── readme_datasetbuilding.md   # Documentazione tecnica completa
└── CLAUDE.md                   # ← questo file (solo regole universali)
```

---

## 4. Comandi operativi

```bash
# ── Script di produzione completati ───────────────────────────────────────
uv run script_prova/fetch_metadati_senato.py --legs 17
uv run script_prova/fetch_metadati_senato.py --force
uv run script_prova/fetch_metadati_camera.py --legs 17
uv run script_prova/fetch_anagrafica_sparql.py --leg 19
uv run script_prova/build_coalizioni.py --validate

# ── Script originali collaboratore (non modificare, solo consultare) ───────
uv run script/senato_pilot.py list-atti --limit 10
uv run script/parser_ddl.py <file>.akn.xml --output <file>.json

# ── Query DuckDB ───────────────────────────────────────────────────────────
duckdb -c "SELECT * FROM t_atti_senato WHERE legislatura=17 LIMIT 5" data/dataset/iter_legis.duckdb
```

---

## 5. Dipendenze

Gestite con `uv` via `pyproject.toml`. Principali: `pandas`, `pyarrow`, `requests`, `duckdb`.

DuckDB COPY TO è il metodo canonico per scrivere Parquet — non richiede `pyarrow` esplicito.
`chardet` è richiesta da T5 per il rilevamento encoding dei file AKN Senato.

---

## 6. Convenzioni di codice

- Header `# /// script` per `uv run` (inline dependencies).
- CLI via `argparse`; ogni script ha `--dry-run` obbligatorio.
- Nomi: `fetch_` = scarica dati, `build_` = tabelle derivate, `diag_` = diagnostica.
- Sleep 1s tra chiamate SPARQL, retry 3× con 5s di attesa.
- Logging strutturato JSON in `data/meta/fetch_log_{nome}.json`.

---

## 7. Convenzioni di commento

- **Lingua**: inglese in tutti gli script (eccetto docstring top-level, bilingue accettato).
- **Cosa commentare obbligatoriamente**:
  - Query SPARQL: proprietà usata, catena, data scoperta diagnostica (ISO 8601)
  - Parametri non ovvi: magic numbers, soglie, chunk size + motivazione
  - Workaround tecnici: causa specifica citata esplicitamente
  - Scrittura Parquet: motivo del DuckDB COPY TO
- **Cosa NON commentare**: codice auto-esplicativo, sequenze ovvie, info già nel docstring.
- Tono: neutro e impersonale ("Returns…", "Filters…", "The endpoint requires…").
- Date nei commenti: formato ISO 8601 (`YYYY-MM-DD`).
- Commenti su riga singola precedono la riga di codice, non la seguono.
