# AGENTS.md — iter-legis

Guida operativa per Codex. Leggere interamente prima di scrivere qualsiasi codice.

> **Questo file è un documento vivente.** Codex deve aggiornarlo ogni volta che scopre fatti nuovi o contraddittori rispetto a quelli qui documentati. Vedi §0 per il protocollo.

---

## 0. Protocollo di auto-aggiornamento

Questo file deve restare accurato nel tempo. Codex ha l'obbligo di aggiornarlo ogni volta che una sessione di lavoro produce conoscenza nuova o contraddittoria rispetto a quanto già documentato.

### Quando aggiornare

Aggiornare AGENTS.md **immediatamente dopo la scoperta** nei seguenti casi:

- Una query SPARQL rivela che una proprietà documentata non esiste, si chiama diversamente, o ha comportamento diverso da quanto scritto.
- Un endpoint (Senato, Camera) risponde con struttura dati inattesa (nuovi campi, URI pattern diversi, errori sistematici).
- Si scopre un nuovo modo di collegare entità nel triplestore (nuova catena di proprietà).
- Un bug viene identificato e risolto: aggiornare §10 (Bug noti) con causa, fix e stato.
- Un task viene completato: aggiornare §7 (Stato avanzamento) spostando il task da "Da fare" a "Completati".
- Un nuovo task viene identificato: aggiungerlo a §7 con descrizione e dipendenze.
- Si scopre una dipendenza tecnica nuova (libreria, header HTTP, formato file).
- Il comportamento di Camera o Senato cambia (rate limiting, URL pattern, autenticazione).

### Come aggiornare

**Prima di modificare AGENTS.md è obbligatorio ottenere conferma esplicita di Giacomo.**

Il flusso corretto è:
1. Identificare la scoperta e la sezione pertinente (§4 per fatti SPARQL, §7 per task, §10 per bug, ecc.).
2. Descrivere a Giacomo cosa si intende aggiornare e perché, in modo sintetico (es. "Ho scoperto che `osr:dataStatoDdl` non esiste — il campo corretto è `osr:dataStatoDdl2`. Aggiorno §4.1?").
3. **Attendere conferma esplicita** ("sì", "procedi", "ok") prima di scrivere qualsiasi modifica al file.
4. Solo dopo la conferma: modificare il contenuto **in modo chirurgico**, senza riscrivere sezioni intere se non necessario.
5. Se una voce esistente è **sbagliata**, correggerla direttamente alla fonte (non aggiungere note di correzione affiancate).
6. Aggiungere una riga al Registro revisioni con data e motivo.

### Registro revisioni

| Data | Sezione modificata | Motivo |
|---|---|---|
| 2026-05-27 | Creazione completa | Prima stesura da sessione Cowork |
| 2026-05-27 | §4.1 `osr:Ddl` | Correzioni da `diag_ddl_unici.py`: osr:idFase esiste (null rate 0%), tabella empirica righe/DDL unici, ⚠️ troncamento Leg13/14/16, proprietà mancanti (testoApprovato, URLTesto, ecc.) |
| 2026-05-27 | §4.1 + §10 | Confermato troncamento Leg13/14/16 con query COUNT. Aggiunta distinzione ramo=S/C e campo natura. Fix: keyset pagination in fetch_metadati_senato.py. |
| 2026-05-27 | §4.1 | Fix verificato: Leg13=13.318, Leg14=10.483, Leg16=9.572 righe corrette. Aggiunta osr:testoApprovato al fetch (copertura 2.6–7.9% per legislature). |
| 2026-05-27 | §4.2 | Riscritta sezione emendamenti: URLTesto=redirect AKN (no formato alternativo), ramo=C sempre 0 (by design), doppio conteggio testi unificati, emendamenti orfani, impossibilità di filtrare per ramo via SPARQL. |
| 2026-05-27 | §10, §13 | Aggiunto bug Parquet format 2.6 vs 2.4 (fix applicato); aggiunta §13 convenzioni di commento in inglese |
| 2026-05-27 | §10, §11, §13 | Corretto fix Parquet: version='2.4' ignorato da pyarrow 24 → fix reale è DuckDB COPY TO (formato 1.0). Aggiunto bug HTTP 403 endpoint Senato. Aggiornata §11 (dipendenza critica: duckdb, non pyarrow). Aggiornato esempio §13. |
| 2026-05-27 | §4.4, §9 | Fix URN prefix: il formato reale è `urn:nir:` non `urn:lex:it:` (confermato da diag_testi_ddl.py). Aggiunto §4.4 testoUnificato = 0 su tutte le legislature. Aggiornato §9 con colonne mancanti urn_testo_approvato / has_testo_approvato. |
| 2026-05-27 | §4.4, §4.6, §10 | Aggiornata pipeline NIR URN Senato (confermata uniforme Leg13-19). Aggiunta §4.6 Camera: allegatoDiscussione, emendamenti come HTML bollettino, join Camera↔Senato ridimensionato. Fix §10: Referer Camera confermato funzionante. Aggiunto encoding emendamenti Senato (Leg14/18/19 diversi). |
| 2026-05-28 | §4.7, §9.2, §10 | Fase esplorativa completa su ocd:atto Camera (diag_camera_atti.py + diag_camera_stato_testo.py). Aggiunti: schema empirico ocd:atto, conteggi reali per leg, cap paginazione confermato, bug triple duplicate Camera, dc:relation ≠ url testo (abbinamento), pipeline versioneTestoAtto, statoIter structure, deputato URI format. |
| 2026-05-28 | §4.7, §10 | T2 completato (fetch_metadati_camera.py). Aggiornato §4.7: dc:identifier non-intero ("105-B", "1061-bis") su atti di navetta, keyset URI obbligatorio. Aggiunto §10: bug URI keyset (fixato) e HTTP 400 su VALUES blocks Camera. |
| 2026-05-28 | §4.7, §7, §10 | Fase diagnostica Leg13-16 (diag_camera_leg13_16.py). Confermato: Leg13-15 prive di linked entities pre-digitale (0% natura/statoIter/vta), genuino e non artefatto fetch. Leg16: natura reale=100% (82.8% era bug VALUES), statoIter genuinamente 0.3%. dc:type "Relazione" ~10% Leg13-14. Aggiunto fix VALUES batch (100 URI). T2 spostato a Completati con nota refetch Leg16. |

*(Aggiungere una riga a ogni aggiornamento significativo.)*

---

## 1. Contesto di tesi

**Obiettivo accademico**: analizzare la relazione tra frammentazione politica e complessità legislativa in Italia nelle legislature 13–19 (1996–oggi). Il dataset costruito in questo progetto è esso stesso un contributo originale della tesi: deve essere solido, riproducibile e predisposto al maggior numero possibile di analisi future.

**Fonti dati primarie**:
- Senato: endpoint SPARQL `https://dati.senato.it/sparql` (prefisso `osr: <http://dati.senato.it/osr/>`)
- Camera: endpoint SPARQL `https://dati.camera.it/sparql` (prefisso `ocd: <http://dati.camera.it/ocd/>`)
- Testi DDL Senato: pipeline NIR URN → PDFServer (vedi §6)
- Testi DDL Camera: PDF statici su `https://www.camera.it/...`
- Testi emendamenti Senato: file AKN via `osr:URLTestoXml`

---

## 2. Regole di lavoro — OBBLIGATORIE

1. **Non modificare mai `script/`**. Quella cartella contiene gli script originali del collaboratore e non va toccata. Per versioni sperimentali/di prova usare `script_prova/` con nomi distinguibili (es. `fetch_metadati_senato_v2.py`).
2. **Gli script esplorativi/diagnostici vanno in `explo_script/`**, mai in `script_prova/`.
3. **Prima di produrre codice, descrivere sempre il piano** e attendere conferma esplicita dell'utente (Giacomo).
4. **Lavorare per task chiuse**: apri un problema, risolvilo, verifica, chiudi, poi passa al prossimo.
5. **Usare Leg17 o Leg18 per i test** (legislature complete e terminate).
6. **Ogni script deve essere idempotente**: controlla esistenza output prima di rieseguire.
7. **Nessun secret o credenziale** va incluso nel codice.
8. **Tutte le query SPARQL usano `uv run`** per la gestione delle dipendenze.

---

## 3. Struttura cartelle

```
iter-legis/
├── script/             # ⛔ INTOCCABILE — script originali collaboratore
├── script_prova/       # Script di produzione nuovi (solo script definitivi)
│   ├── fetch_metadati_senato.py     ✅ completato
│   ├── fetch_anagrafica_sparql.py   ✅ completato
│   └── build_coalizioni.py          ✅ completato
├── explo_script/       # Script esplorativi/diagnostici (usa e getta)
│   ├── diag_sparql_senato.py
│   ├── diag_emendamenti_senato.py
│   ├── diag_oggetto_trattazione.py
│   └── diag_date_temporali.py
├── data/
│   ├── raw/
│   │   ├── senato/     # PDF testi presentati e file AKN emendamenti
│   │   └── camera/     # PDF testi presentati Camera
│   ├── meta/           # Parquet/CSV metadati strutturati
│   │   ├── atti_senato.parquet        (output di fetch_metadati_senato.py)
│   │   ├── coverage_senato.parquet
│   │   ├── fetch_log_senato.json
│   │   ├── atti_camera.parquet        (da costruire)
│   │   └── coverage_camera.parquet    (da costruire)
│   ├── text/           # Testo estratto .txt + .extract.json
│   └── dataset/        # Dataset analitico finale
│       └── iter_legis.duckdb
├── docs/
├── PRD.md
├── README.md
├── schema.json
└── AGENTS.md           # ← questo file
```

---

## 4. Fatti tecnici critici sul triplestore Senato

Queste scoperte provengono da sessioni di diagnostica SPARQL. Ignorarle causa errori silenziosi.

### 4.1 `osr:Ddl` — struttura

**Cos'è `osr:Ddl`**: rappresenta un Disegno di Legge ed è la classe fondamentale per tutto l'iter legislativo (definizione ontologia ufficiale). Non è una "fase" in senso atomico: è il DDL stesso, ma uno stesso DDL fisico può generare **più istanze** nel triplestore — una per ogni passaggio tra Camera e Senato (navette inter-camerali), tracciate da `osr:progressivoIter`.

**Dati empirici** (da `diag_ddl_unici.py` su `atti_senato.parquet`, Leg13–19):

| Leg | Righe totali | DDL unici (idDdl) | fasi/DDL | % multifase |
|-----|-------------|-------------------|----------|-------------|
| 13  | 10.000 ⚠️  | 9.028             | 1.11     | 9.7%        |
| 14  | 10.000 ⚠️  | 9.029             | 1.11     | 9.7%        |
| 15  | 5.568       | 5.395             | 1.03     | 3.1%        |
| 16  | 3.000 ⚠️   | 2.856             | 1.05     | 4.8%        |
| 17  | 8.004       | 7.443             | 1.08     | 6.8%        |
| 18  | 6.479       | 6.059             | 1.07     | 4.9%        |
| 19  | 4.913       | 4.490             | 1.09     | 6.6%        |

⚠️ **Leg13, Leg14 e Leg16 sono troncate** — confermato con query COUNT (vedi `diag_count_reale_leg13_14.py`):

| Leg | Triplestore (reale) | Fetch vecchio   | Fetch corretto | ramo=S | ramo=C |
|-----|---------------------|-----------------|----------------|--------|--------|
| 13  | 13.318 ✅           | 10.000 (troncato) | 13.318       | 5.339  | 7.979  |
| 14  | 10.483 ✅           | 10.000 (troncato) | 10.483       | 3.975  | 6.508  |
| 15  | 5.568 ✅            | 5.568 (ok)      | 5.568          | 2.056  | 3.512  |
| 16  | 9.572 ✅            | 3.000 (troncato) | 9.572         | 3.748  | 5.824  |
| 17  | 8.004 ✅            | 8.004 (ok)      | 8.004          | 3.096  | 4.908  |
| 18  | 6.479 ✅            | 6.479 (ok)      | 6.479          | 2.719  | 3.760  |
| 19  | 4.913 ✅            | 4.913 (ok)      | 4.913          | 1.946  | 2.967  |

L'endpoint Senato SPARQL ha un **cap sul totale dei risultati restituibili per query** (Virtuoso `ResultSetMaxRows`). La paginazione LIMIT/OFFSET si blocca quando l'OFFSET supera il cap. **Fix applicato**: keyset pagination — `FILTER(?id_fase > {last_id}) ORDER BY ?id_fase` — ogni pagina parte dall'ultimo ID visto, l'endpoint la tratta come query nuova. Implementato in `fetch_metadati_senato.py` dal 2026-05-27.

**Proprietà disponibili** (dall'ontologia ufficiale `http://dati.senato.it/osr/Ddl`):
`osr:assegnazione`, `osr:relatore`, `osr:URLTesto`, `osr:dataPresentazione`, `osr:dataStatoDdl`, `osr:fase`, `osr:idDdl`, `osr:idFase`, `osr:legislatura`, `osr:natura`, `osr:numeroFase`, `osr:numeroFaseCompatto`, `osr:presentatoTrasmesso`, `osr:progressivoIter`, `osr:statoDdl`, `osr:titolo`, `osr:testoPresentato`, `osr:testoApprovato`

**Proprietà non ancora fetchate** (esistono nell'ontologia, assenti dal parquet):
- `osr:testoApprovato` — testo approvato definitivamente (**da aggiungere a DDL_QUERY**)
- `osr:URLTesto` — URL generico al testo (diverso da testoPresentato, da esplorare)
- `osr:numeroFaseCompatto` — versione compatta del numero di fase
- `osr:assegnazione` — commissione assegnata
- `osr:relatore` — relatore del DDL

**Distinzione ramo_origine — importante per le analisi**:
- `ramo_origine = S`: atto presentato al Senato. Il testo presentato è nel triplestore Senato.
- `ramo_origine = C`: atto originato alla Camera e trasmesso al Senato. Il testo non è nel triplestore Senato (risiede sul sito Camera). Circa **2/3 degli atti hanno ramo=C**.
- Per analisi sul Senato "puro": filtrare `ramo_origine = 'S'`.
- Il campo `osr:natura` distingue il tipo di atto (`DDL`, `PDL`, `DL`, `DDLC`, ratifiche, ecc.) — usarlo per filtrare per tipo di iniziativa legislativa.

**Note tecniche**:
- `osr:idFase` **esiste** come proprietà SPARQL esplicita (null rate 0%, coincide 100% con l'ID estratto dall'URI). È chiave della keyset pagination.
- **URI pattern**: `http://dati.senato.it/ddl/{idFase}` — non `/osr/ddl/`.
- `osr:idDdl` è l'ID del DDL complessivo (uguale per tutte le fasi dello stesso disegno di legge).
- `osr:numeroFase` è il numero visibile (es. "601" come in "S.601").
- **`osr:numero` NON esiste** su `osr:Ddl` — usarlo causa 0 risultati.
- **`osr:dataPresenta` NON esiste** — il campo corretto è `osr:dataPresentazione`.
- `osr:legislatura` è `xsd:integer` → usare `19` non `"19"` nelle query.
- **Per analisi su DDL unici**: filtrare su `is_prima_fase = True` (oppure `progressivo_iter = 1`). Le navette sono il 3–10% dei record a seconda della legislatura.

### 4.2 `osr:Emendamento` — struttura, linking e qualità dei dati

**Struttura base:**
- `osr:Emendamento` **non ha un link diretto** al DDL.
- La catena di collegamento è:
  ```
  osr:Emendamento → osr:oggetto → osr:OggettoTrattazione → osr:relativoA → osr:Ddl
  ```
- `osr:Emendamento` **non ha campi data** (proprietà: label, oggetto, legislatura, tipo, numero, URLTesto, flagCommissione, URLTestoXml).
- La data di un emendamento si ricava tramite `osr:seduta` → `osr:Votazione` → `osr:SedutaAssemblea`.

**Testi disponibili:**
- `osr:URLTestoXml` → file AKN diretto (es. `http://www.senato.it/leg/17/BGT/Testi/Emend/…/….akn`)
- `osr:URLTesto` → URL redirect `.asp` che punta allo **stesso file AKN**. Non è un formato alternativo.
- **Tutti gli emendamenti nel triplestore hanno entrambe le proprietà popolate (100%)** — non esiste un formato non-AKN separato.
- `tipodoc=emend` negli URL = emendamento in aula; `tipodoc=emendc` = emendamento in **commissione** (non "Camera"). Il campo `osr:flagCommissione` distingue i due casi.

**Emendamenti Camera vs Senato:**
- **Tutti gli emendamenti in `dati.senato.it` sono emendamenti proposti al Senato** — per definizione.
- Il `ramo` su `osr:Ddl` indica chi ha *prodotto* quella versione del testo, non chi sta esaminando. Quando il Senato modifica un DDL (anche di origine Camera), crea una fase `ramo=S` e gli emendamenti si collegano a quella.
- **ramo=C ha sempre 0 emendamenti nel parquet** — non è un bug: le fasi ramo=C sono versioni Camera, il Senato non propone emendamenti su di esse (li propone sulla fase ramo=S successiva).
- Gli emendamenti proposti **alla Camera** stanno in `dati.camera.it` → Task 6 futuro.

**Qualità dei dati — copertura per legislatura** (da `diag_emend_formati.py` + `diag_emend_count_gap.py`):

| Leg | Tot. triplestore | Parquet (tutti DDL) | Coverage | Note |
|-----|-----------------|---------------------|----------|------|
| 13  | 709             | 143                 | 20%      | Leg pre-digitale; pochissimi DDL con emend. nella catena di linking |
| 14  | 86.147          | 78.006              | 90.5%    | Gap ~8k spiegato da emendamenti orfani |
| 15  | 33.652          | 32.700              | 97.2%    | ✅ |
| 16  | 116.909         | 161.324             | **138%** | ⚠️ Doppio conteggio: testi unificati |
| 17  | 253.387         | 253.816             | ~100%    | ✅ (piccolo doppio conteggio) |
| 18  | 151.262         | 148.598             | 98.2%    | ✅ |
| 19  | 53.337          | 53.558              | ~100%    | ✅ (parziale — leg. in corso) |

**Cause del gap e del doppio conteggio:**
- **Emendamenti orfani** (~6-9% per le legislature grandi): emendamenti nel triplestore la cui catena `osr:oggetto → osr:relativoA` è spezzata. Non recuperabili. Leg16: 6.906; Leg17: 21.613.
- **Doppio conteggio** (coverage >100%): alcuni emendamenti sono collegati a più DDL (es. testi unificati, assorbimenti). La `EMEND_COUNT_QUERY` usa `COUNT(DISTINCT ?emend) GROUP BY ?ddl`, ma un emendamento che appare in due DDL viene sommato due volte nel totale di legislatura.

**Come correggere il doppio conteggio nelle analisi:**
Non sommare `n_emendamenti` dal parquet per ottenere il totale di legislatura — il risultato è inflato per Leg16/17. Usare invece una query SPARQL con `COUNT(DISTINCT ?emend)` senza `GROUP BY ?ddl`, oppure al momento del download dei testi fare deduplicazione per `id_emendamento`.

**Query SPARQL che filtra per ramo non funziona** (restituisce 0):
Il filtro `?ddl osr:ramo "S"` nella SPARQL non matcha per tipo di letterale. Usare invece il join con il parquet in post-processing (pandas/DuckDB) per filtrare per ramo.

### 4.3 `osr:Votazione` — struttura

- Ha dati **per singolo senatore**: favorevole/contrario/astenuto/presente.
- Ha `osr:esito`, link a `osr:seduta`, conteggi presenti/votanti/maggioranza.
- La data della votazione si ottiene navigando: `osr:seduta` → `osr:SedutaAssemblea` → proprietà data.
- Utile per: analisi di voto, timeline iter, allineamento temporale con affiliazioni parlamentari.

### 4.4 Testo presentato — regola per ramo

| `ramo_origine` | Dove sta il testo | Come recuperarlo |
|---|---|---|
| `S` (Senato) | Triplestore Senato (`osr:testoPresentato` = NIR URN) | NIR URN → HTML intermedio → PDF |
| `C` (Camera) | Sito Camera (HTML/PDF) | `getDocumento.ashx` con header Referer |

**Pipeline NIR URN Senato (confermata uniforme Leg13–19, testata su Leg13 e Leg19):**
```
URN → https://www.senato.it/uri-res/N2Ls?{urn} → pagina HTML con link → PDF/PDFServer/BGT/{id}.pdf
```
Il campo `osr:testoPresentato` contiene sempre un NIR URN nel formato:
```
urn:nir:senato.repubblica:disegno.legge:{N}.legislatura;{numero}
```
Il numero finale può contenere lettere (es. `813-B` per DDL in navette). Il prefisso è **`urn:nir:`**, non `urn:lex:it:`. Non esiste differenza di pipeline tra Leg13–16 e Leg17–19: la risoluzione URN è uniforme.

**Copertura ~38% — non è dato mancante.** Il ~60% senza `testoPresentato` sono quasi interamente DDL `ramo=C` (il testo sta sul lato Camera). I DDL `ramo=S` hanno copertura quasi totale (98.6–99.9% per legislatura). La copertura totale bassa è una conseguenza della proporzione ramo=C nel dataset (≈60%).

**Pipeline Camera (da T4):**
- `getDocumento.ashx` restituisce il documento correttamente aggiungendo `Referer: http://documenti.camera.it/` alla richiesta HTTP. Una riga di codice.

**`osr:testoUnificato` — non popolato nel triplestore**: COUNT = 0 per tutte le legislature (Leg13–19). Il predicato esiste nell'ontologia ma non viene usato. Ignorare in tutte le pipeline di fetch e analisi.

### 4.5 Encoding testi emendamenti Senato

I file AKN degli emendamenti Senato non hanno encoding uniforme. Confermato su file reali:

| Legislatura | Encoding |
|---|---|
| Leg14 | UTF-8 con BOM |
| Leg18 | UTF-16 LE |
| Leg19 | ISO-8859-1 |

**Fix**: usare una funzione `detect_and_decode(bytes)` che rileva il BOM prima del parsing. Circa 5 righe con la libreria `chardet`. Da applicare in T5 (`fetch_emendamenti_senato.py`) e in tutti gli script che leggono file AKN.

### 4.6 Camera — emendamenti e join Camera↔Senato

**Emendamenti Camera — struttura `ocd:allegatoDiscussione`** (da `diag_camera_emendamenti.py` e `diag_camera_allegati_url.py`, 2026-05-27):

Gli emendamenti Camera non sono entità individuali come al Senato. Sono **allegati collettivi ai bollettini di seduta**, class `ocd:allegatoDiscussione`. Ogni allegato contiene una lista di emendamenti discussi in quella seduta.

Catena ontologica confermata (ontologia Camera v1.2):
```
ocd:atto
  ← ocd:rif_attoCamera (su ocd:dibattito)
ocd:dibattito
  → ocd:rif_discussione → ocd:discussione
  → ocd:rif_allegatoDiscussione → ocd:allegatoDiscussione
    → dc:relation → URL bollettino HTML (~44 KB)
```

Proprietà disponibili su `ocd:allegatoDiscussione`: `rdf:type`, `dc:title`, `rdfs:label`, `dc:relation` (URL), `ocd:rif_leg`, `ods:modified`.

Copertura per legislatura:

| Leg | Totale allegati | Con emend | % |
|---|---|---|---|
| 13–15 | 0 | 0 | — (pre-digitale, non in triplestore) |
| 16 | 989 | 291 | 29.4% |
| 17 | 11.841 | 1.575 | 13.3% |
| 18 | 9.044 | 1.001 | 11.1% |
| 19 | 7.030 | 912 | 13.0% |

**Formato URL bollettino** (`dc:relation`):
```
https://documenti.camera.it/apps/commonServices/getDocumento.ashx?sezione=bollettini&tipoDoc=allegato&idLegislatura={N}&anno=...&idcommissione=...&pagina={ancora}&ancora={ancora}
```
Il GET restituisce **HTML** (~44 KB), non PDF. Il parametro `ancora` è l'anchor HTML che identifica la sezione specifica dell'allegato nel bollettino. Richiede parsing HTML per estrarre il testo degli emendamenti. Aggiungere header `Referer: http://documenti.camera.it/`.

**URI legislatura Camera** (formato corretto):
```
http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}
```
Non `legislatura/{N}` — causa 0 risultati nelle query SPARQL.

**Join Camera↔Senato — ridimensionato:**
- `ocd:rif_attoSenato` non è una proprietà sugli atti in generale: è sulle **trasmissioni** (navette inter-camerali). Il valore è un URL HTML, non un URI RDF del triplestore Senato.
- Copre circa 544 trasmissioni (non 624 come stimato in precedenza).
- Per gli atti che non transitano tra i rami, Camera e Senato sono **popolazioni separate** — il join non serve. Costruire le due tabelle (`t_atti_senato`, `t_atti_camera`) come entità indipendenti; il collegamento si applica solo per le navette.

### 4.7 Camera — `ocd:atto`: schema empirico (da `diag_camera_atti.py` + `diag_camera_stato_testo.py`, 2026-05-28)

#### Conteggi reali per legislatura

⚠️ **Il triplestore Camera ha triple RDF duplicate**: ogni atto appare due volte con `rdf:type ocd:atto` e `ocd:rif_leg`. `COUNT(*)` restituisce il doppio del reale; usare sempre `COUNT(DISTINCT ?atto)` e `SELECT DISTINCT ?atto`.

| Leg | COUNT(DISTINCT) reale | Note |
|-----|----------------------|------|
| 13  | 8.281  | |
| 14  | 7.180  | |
| 15  | 3.618  | |
| 16  | 5.817  | |
| 17  | 4.903  | |
| 18  | 3.757  | |
| 19  | 2.965  | |

Totale triplestore senza filtro leg: 269.633 — include legislature del **Regno d'Italia** (pre-1948, pattern URI `legislatura.rdf/regno_{N}`). Filtrare sempre su `repubblica_{N}`.

#### Cap paginazione

Confermato identico al Senato: **OFFSET ≥ 10.000 → errore** (corpo risposta vuoto, JSON parse error). Keyset pagination obbligatoria.

**Keyset: usare URI, non `dc:identifier` intero.** Alcuni atti hanno `dc:identifier` non-intero (navette e varianti: "105-B", "1061-bis", "244-quinquies", ecc.). Il filtro `FILTER(xsd:integer(?id) > N)` li esclude silenziosamente. Leg13 ha ~1.199 atti non-interi su 8.281 totali (14.5%). Confermato (2026-05-28).

**Strategia corretta** (implementata in `fetch_metadati_camera.py`):
```sparql
FILTER(STR(?atto) > "{last_atto}") ORDER BY STR(?atto) LIMIT 500
```
L'ordinamento è lessicografico sugli URI — totale e senza buchi, tutti gli atti vengono raggiuti indipendentemente dal formato di `dc:identifier`.

#### Formato `ocd:rif_leg`

URI senza datatype: `http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}`. Usare `<URI>` nei FILTER, non letterali.

#### Proprietà disponibili su `ocd:atto` (schema empirico Leg17, N=4.903)

| Proprietà | Copertura | Tipo valore | Note |
|---|---|---|---|
| `dc:identifier` | ~100% | stringa ("1", "42", "105-B", "1061-bis") | chiave keyset URI — vedi nota sotto |
| `dc:title` | ~100% | stringa | titolo esteso dell'atto |
| `dc:date` | ~100% | stringa YYYYMMDD | data presentazione |
| `dc:type` | ~100% | stringa | "Progetto di Legge" |
| `ocd:rif_natura` | ~100% | URI linked entity | `natura.rdf/proposta_legge_ordinaria` |
| `ocd:iniziativa` | ~100% | stringa | "Parlamentare", "Governativa", "Popolare" |
| `ocd:rif_statoIter` | ~100% | URI linked entity, **multivalore** avg 6.4 (lordi) | storia stati iter |
| `ocd:rif_versioneTestoAtto` | ~99% | URI linked entity, **multivalore** avg ~2.5 | versioni del testo |
| `dc:relation` | ~99% | URL PDF, **multivalore** ⚠️ | vedi nota sotto |
| `ocd:primo_firmatario` | ~98% | URI deputato, multivalore | `deputato.rdf/d{id}_{leg}` |
| `ocd:rif_assegnazione` | ~92% | URI linked entity | commissione assegnata |
| `dc:contributor` | ~62% | URI | altri firmatari |
| `ocd:rif_dibattito` | ~34% | URI linked entity, multivalore | |
| `ocd:rif_relatore` | ~32% | URI linked entity | |
| `ocd:rif_richiestaParere` | ~26% | URI linked entity | |
| `ocd:rif_abbinamento` | ~23% | URI atto abbinato, multivalore | |
| `ocd:rif_trasmissione` | ~15% | URI linked entity | navetta al Senato |
| `dc:description` | ~9%  | stringa | |
| `dcterms:isReferencedBy` | ~100% | URL scheda Camera | |
| `ods:modified` | ~100% | timestamp ISO 8601 | |

**Proprietà assenti (confermate 0 risultati):** `ocd:titolo`, `ocd:numero`, `ocd:ramo`, `ocd:dataPresentazione`, `ocd:ac`, `ocd:rif_tipoAtto`, `ocd:rif_iter`. Non usarle nelle query.

#### ⚠️ `dc:relation` sull'atto NON è l'URL del suo testo

`dc:relation` su `ocd:atto` aggrega i PDF di **tutti gli atti abbinati in discussione congiunta**. Gli atti abbinati possono avere decine o centinaia di URL (ac17_2680 = 171 URL distinti, tutti di atti diversi). Non è usabile per recuperare il testo di quell'atto specifico.

**Pipeline corretta per il testo presentato:**
```
ocd:atto → ocd:rif_versioneTestoAtto (MIN dc:date) → dcterms:isReferencedBy → URL getDocumento.ashx
```
La `versioneTestoAtto` con `MIN(dc:date)` è sempre la versione originale presentata. Il suo `dcterms:isReferencedBy` punta all'URL scaricabile (richiede `Referer: http://documenti.camera.it/` — vedi §10).

#### Struttura `ocd:statoIter`

Ogni istanza ha: `rdfs:label` (es. "Assegnato", "Approvato definitivamente. Legge"), `dc:date` (YYYYMMDD), `ods:modified`. Per ottenere **l'ultimo stato** di un atto: prendere la `ocd:rif_statoIter` con `MAX(dc:date)`.

Valori `rdfs:label` più frequenti in Leg17:
`"Da assegnare"`, `"Assegnato"`, `"In corso di esame in Commissione"`, `"Concluso l'esame da parte della Commissione"`, `"In discussione"`, `"Approvato. Trasmesso al Senato"`, `"Approvato definitivamente. Legge"`, `"Ritirato"`, `"Assorbito dall'approvazione di pdl abbinato"`.

#### Struttura `ocd:versioneTestoAtto`

Ogni istanza ha: `rdfs:label` (es. "Disegno di Legge presentato il 24 luglio 2008"), `dc:date` (YYYYMMDD), `dcterms:isReferencedBy` (URL getDocumento.ashx). Il codice nell'URI (es. `vta17_17PDL0000010`) corrisponde allo stampato Camera.

#### `ocd:primo_firmatario` — URI deputato

Formato: `http://dati.camera.it/ocd/deputato.rdf/d{id}_{leg}`. Ogni URI ha `foaf:firstName`, `foaf:surname`, `rdfs:label` (nome + legislatura), `ocd:rif_mandatoCamera`. Permette join futuro con `t_deputati`.

#### `ocd:rif_natura` — distribuzione Leg17

| URI (last segment) | rdfs:label | N atti |
|---|---|---|
| `proposta_legge_ordinaria` | "Proposta di legge ordinaria" | 4.323 |
| `disegno_legge_ordinario` | "Disegno di legge ordinario" | 372 |
| `proposta_legge_costituzionale` | "Proposta di legge costituzionale" | 202 |
| `disegno_legge_costituzionale` | (no rdfs:label, ma dc:title presente) | 6 |

#### Pattern URL PDF

Dominio varia per legislatura:
- Leg13–17: `http://www.camera.it/_dati/leg{N}/lavori/stampati/pdf/{code}.pdf`
- Leg18–19: `http://documenti.camera.it/_dati/leg{N}/lavori/stampati/pdf/{code}.pdf`

#### Copertura linked entities per legislatura — limitazioni Leg13-16

Confermato da query COUNT dirette sull'endpoint Camera (diag_camera_leg13_16.py, D1 + D5, 2026-05-28). I valori 0% per Leg13-15 sono **genuini** (dati pre-digitale non immessi nel triplestore), non artefatti del fetch.

| Proprietà | Leg13 | Leg14 | Leg15 | Leg16 | Leg17 |
|---|---|---|---|---|---|
| `dc:title` | 100% | 100% | 100% | 100% | 100% |
| `dc:date` | ~97% | ~100% | ~100% | ~100% | ~100% |
| `dc:type` | 100% | 100% | 100% | 100% | 100% |
| `ocd:iniziativa` | ~90% | ~90% | ~90% | ~100% | ~100% |
| `ocd:primo_firmatario` | ~90% | ~90% | ~90% | ~95% | ~98% |
| `ocd:rif_natura` | **0%** | **0%** | **0%** | 100%† | ~100% |
| `ocd:rif_statoIter` | **0%** | **0%** | **0%** | **0.3%** | ~100% |
| `ocd:rif_versioneTestoAtto` | **0%** | **0%** | **0%** | **0.1%** | ~99% |
| `dc:relation` (URL PDF diretto) | ~90% | ~90% | ~90% | — | — |

†Leg16 natura=82.8% nel parquet corrente a causa del bug HTTP 400 su VALUES block (vedere §10). Valore reale=100% — Leg16 va rifetchata con batch più piccolo.

**Leg13-15 — testo via `dc:relation` diretto (non via `ocd:rif_versioneTestoAtto`):**

Per le legislature pre-digitali, il PDF del testo presentato è accessibile direttamente su `dc:relation` dell'atto con URL nel formato:
```
http://www.camera.it/_dati/leg{N}/lavori/stampati/pdf/{NNNN}.pdf
```
(codice a 4 cifre zero-padded, diverso dal formato Leg17+ `{N}PDL{code}.pdf`). Non usare la pipeline `ocd:rif_versioneTestoAtto → dcterms:isReferencedBy` per Leg13-15: quella catena ha copertura 0%.

**`dc:type "Relazione"` in Leg13-14 (~10% degli atti):**

Leg13 e Leg14 contengono circa il 10% di atti con `dc:type = "Relazione"`. Questi non sono proposte di legge ma atti parlamentari di rendicontazione (relazioni di commissioni, relazioni di governo). Da filtrare nelle analisi che richiedono solo proposte di legge (`dc:type = "Progetto di Legge"`). Confermato D6 (2026-05-28).

**Non-integer `dc:identifier` per legislatura (D2, 2026-05-28):**

| Leg | Atti totali | ID non-interi | % |
|---|---|---|---|
| 13 | 8.281 | ~1.199 | ~14.5% |
| 14 | 7.180 | ~70 | ~1% |
| 15–19 | — | <0.5% | trascurabile |

Leg13 ha la concentrazione maggiore (navette della XII legislatura). Il keyset URI (già implementato) gestisce correttamente tutti i formati.

**Leg16 `ocd:rif_statoIter` = 0.3% genuino:**

17 atti su 5.820 hanno statoIter nel triplestore. Non è un artefatto — confermato da COUNT diretto (D5). La Leg16 è strutturalmente priva di dati iter analizzabili.

#### Usabilità Leg13-16 per le analisi della tesi

| Variabile richiesta dall'analisi | Leg13-15 | Leg16 | Leg17-19 |
|---|---|---|---|
| Complessità testuale dal PDF (Gulpease, lunghezza, riferimenti) | ✅ parziale (dc:relation ~90%, URL format diverso) | ✅ parziale | ✅ via versioneTestoAtto |
| Durata iter (data presentazione → approvazione) | ❌ (0% statoIter) | ❌ (0.3% statoIter) | ✅ |
| Status approvazione (legge / decaduto) | ❌ | ❌ | ✅ |
| Filtraggio per tipo atto (PDL vs DDL) | ❌ (0% natura) + ~10% "Relazione" | ✅ (100% natura†) | ✅ |
| Linkage con frammentazione politica | ✅ | ✅ | ✅ |

**Raccomandazione operativa**: il corpo principale dell'analisi (che richiede iter + approvazione + tipo atto) deve usare **Leg17-19**. Leg16 può contribuire alle analisi che non richiedono iter. Leg13-15 possono comparire nelle statistiche descrittive (numero atti, tipo iniziativa) ma non nell'analisi multivariata principale.

### 4.8 `osr:FaseIter` e `osr:SedutaCommissione`

- Entità esistenti nel triplestore ma **le query GROUP BY su di esse restituiscono HTTP 400**.
- Per esplorare queste classi usare query senza GROUP BY + HAVING.
- `osr:FaseIter` linka a DDL tramite `osr:relativoA`.

---

## 5. Schema dataset — tabelle previste

Il dataset finale deve supportare analisi di complessità legislativa e frammentazione politica.

### Tabelle già progettate (livello metadati)

| Tabella | Chiave | Contenuto |
|---|---|---|
| `t_atti_senato` | `id_fase` | Metadati DDL Senato (da `atti_senato.parquet`) |
| `t_atti_camera` | `id_atto` | Metadati DDL Camera (da costruire) |
| `t_senatori` | `id_senatore × periodo` | Anagrafica senatori con storico gruppi (da `fetch_anagrafica_sparql.py`) |
| `t_coalizioni` | `legislatura × gruppo` | Lookup maggioranza/opposizione (da `build_coalizioni.py`) |

### Tabelle da costruire (livello testi e analisi)

| Tabella | Chiave | Contenuto |
|---|---|---|
| `t_emendamenti` | `id_emendamento` | Metadati emendamenti (conta, gruppo proponente, articolo target) |
| `t_votazioni` | `id_votazione` | Risultati votazioni in aula con date |
| `t_fasi_iter` | `id_fase_iter` | Timeline iter (presentazione → commissione → aula → voto finale) |
| `t_testi` | `id_atto × tipo_testo` | Riferimenti ai file raw (testo presentato, approvato) |

### Testi da raccogliere

1. **Testo presentato** (DDL originale): PDF Senato (ramo=S) o PDF Camera (ramo=C)
2. **Testo emendamenti**: file AKN via `osr:URLTestoXml`
3. **Testo approvato** (legge promulgata): da NormAttiva o Gazzetta Ufficiale

---

## 6. Comandi operativi

```bash
# ── Script di produzione ───────────────────────────────────────────────────

# Metadati DDL Senato (Task 1 — completato)
uv run script_prova/fetch_metadati_senato.py --legs 17          # test su Leg17
uv run script_prova/fetch_metadati_senato.py --force            # tutte le legislature
uv run script_prova/fetch_metadati_senato.py --dry-run          # stampa query, non esegue
uv run script_prova/fetch_metadati_senato.py --no-emend         # salta conteggio emendamenti

# Anagrafica senatori (completato)
uv run script_prova/fetch_anagrafica_sparql.py --leg 19
uv run script_prova/fetch_anagrafica_sparql.py --leg-start 13 --leg-end 19 --skip-existing

# Coalizioni (completato)
uv run script_prova/build_coalizioni.py
uv run script_prova/build_coalizioni.py --validate

# ── Script originali collaboratore (non modificare, solo consultare) ───────

uv run script/senato_pilot.py list-atti --limit 10
uv run script/parser_ddl.py <file>.akn.xml --output <file>.json
uv run script/consolidate_atto.py Atto00055193 --leg 19

# ── Query DuckDB ───────────────────────────────────────────────────────────

duckdb -c "SELECT * FROM t_atti_senato WHERE legislatura=17 LIMIT 5" data/dataset/iter_legis.duckdb
```

---

## 7. Stato avanzamento task

### ✅ Completati

| Task | Script | Output |
|---|---|---|
| T0 — Struttura cartelle e pulizia | — | cartelle `script_prova/`, `explo_script/`, `data/meta/`, `data/raw/` |
| T1 — Metadati DDL Senato (Leg13–19) | `fetch_metadati_senato.py` | `data/meta/atti_senato.parquet` |
| T-Ana — Anagrafica senatori (Leg13–19) | `fetch_anagrafica_sparql.py` | `data/Leg{N}/Anagrafica/senatori_{N}.json` |
| T-Coal — Tabella coalizioni/maggioranza | `build_coalizioni.py` | `data/coalizioni_leg13_19.csv` |
| T2 — Metadati atti Camera (Leg13–19) | `fetch_metadati_camera.py` | `data/meta/atti_camera.parquet` — ⚠️ Leg16 natura parziale (bug VALUES, vedi T2-fix) |

### 🔴 Da fare — in ordine di priorità

#### T2-fix — Refetch Leg16 con VALUES batch ridotto (PROSSIMO)

Il parquet `atti_camera.parquet` per Leg16 ha `natura=null` su ~1.000 atti (82.8% invece di 100%) a causa di HTTP 400 su VALUES block di 500 URI nelle Query B/C/D. Il fix è ridurre il batch size a **100 URI** per le sub-query con VALUES e rifetchare Leg16 con `--force`.

**File da modificare**: `script_prova/fetch_metadati_camera.py`
**Modifica**: parametrizzare `BATCH_SIZE_VALUES` (default 100) e chunking delle liste `atti_uris` nelle Query B, C, D.
**Esecuzione**: `uv run script_prova/fetch_metadati_camera.py --legs 16 --force`
**Verifica**: Leg16 deve avere natura non-null per tutti i 5.817 atti.

#### T3 — `fetch_testi_presentati_senato.py`

Scaricare i PDF dei testi presentati per i DDL Senato con `ramo_origine=S`.

**Pipeline**:
1. Leggere `atti_senato.parquet` filtrando `has_testo_presentato=True AND is_prima_fase=True AND ramo_origine='S'`
2. Convertire il NIR URN in URL PDFServer Senato
3. Scaricare PDF → `data/raw/senato/{id_fase}/testo_presentato.pdf`
4. Salvare `.meta.json` accanto al PDF (fonte, data_fetch, urn, url_effettivo, size_bytes, sha256)
5. Aggiornare `data/meta/fetch_log_testi_senato.json`

**Nota**: rispettare rate limiting (sleep tra download), retry su errori.

#### T4 — `fetch_testi_presentati_camera.py`

Scaricare i PDF dei testi presentati per i DDL con `ramo_origine=C`.

**Pipeline**:
1. Recuperare URL PDF dal lato Camera (da SPARQL Camera o da metadati camera)
2. Scaricare PDF → `data/raw/camera/{id_atto}/testo_presentato.pdf`
3. Stesso pattern `.meta.json` di T3

#### T5 — `fetch_emendamenti_senato.py`

Scaricare i file AKN degli emendamenti Senato.

**Pipeline**:
1. Leggere `atti_senato.parquet` filtrando `has_emendamenti_akn=True`
2. Per ogni DDL: query SPARQL per ottenere lista emendamenti con `osr:URLTestoXml`
3. Scaricare file AKN → `data/raw/senato/{id_fase}/emendamenti/{id_emend}.akn.xml`
4. Salvare `.meta.json` per ogni file

#### T6 — `fetch_emendamenti_camera.py`

Scaricare i testi degli emendamenti Camera (HTML bundle con Referer header obbligatorio).

#### T7 — Tabelle temporali: `t_fasi_iter` e `t_votazioni`

Estrarre dal triplestore Senato:
- `osr:FaseIter` → timeline fasi iter (presentazione, commissione, aula, voto)
- `osr:Votazione` → risultati votazioni per senatore, con data via `osr:SedutaAssemblea`

**Nota**: le query GROUP BY su `osr:FaseIter` restituiscono HTTP 400. Usare approccio alternativo senza HAVING.

#### T8 — `build_dataset_analitico.py`

Assemblare le tabelle in DuckDB per analisi:
- Join `t_atti` × `t_senatori` × `t_coalizioni` su (legislatura, gruppo, data)
- Aggiungere colonne calcolate: `giorni_iter`, `n_emendamenti_per_articolo`, `pct_emend_maggioranza`

#### T9 — Misure di complessità testuale

Da definire con Giacomo. Candidati:
- Indici di leggibilità (Gulpease, Flesch-Kincaid adattato)
- Conteggio riferimenti normativi interni/esterni
- Lunghezza media degli articoli / numero commi
- Similarity testuale tra emendamenti (embedding o TF-IDF)

---

## 8. Architettura dati — 4 livelli

```
Livello 0 — Raw files
  data/raw/senato/{id_fase}/testo_presentato.pdf
  data/raw/senato/{id_fase}/testo_presentato.pdf.meta.json
  data/raw/senato/{id_fase}/emendamenti/{id_emend}.akn.xml
  data/raw/camera/{id_atto}/testo_presentato.pdf

Livello 1 — Metadati strutturati (Parquet)
  data/meta/atti_senato.parquet
  data/meta/atti_camera.parquet
  data/meta/coverage_senato.parquet
  data/meta/coverage_camera.parquet

Livello 2 — Testo estratto
  data/text/{id_fase}/testo_presentato.txt
  data/text/{id_fase}/testo_presentato.extract.json  (metadati estrazione)

Livello 3 — Dataset analitico
  data/dataset/iter_legis.duckdb
    ├── t_atti_senato
    ├── t_atti_camera
    ├── t_senatori
    ├── t_coalizioni
    ├── t_emendamenti
    ├── t_votazioni
    ├── t_fasi_iter
    └── t_testi
```

---

## 9. Schema colonne — `atti_senato.parquet`

Prodotto da `fetch_metadati_senato.py`.

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_fase` | str | ID fase (ultimo segmento URI: `http://dati.senato.it/ddl/{id_fase}`) |
| `id_ddl_interno` | str | `osr:idDdl` — ID DDL complessivo (uguale per tutte le fasi) |
| `id_fase_sparql` | str | `osr:idFase` (dovrebbe coincidere con `id_fase`) |
| `uri_ddl` | str | URI completo nel triplestore |
| `legislatura` | int | Numero legislatura (13–19) |
| `progressivo_iter` | int | 1 = prima fase (presentazione originale), 2+ = fasi successive |
| `is_prima_fase` | bool | True se `progressivo_iter == 1` |
| `numero_fase` | str | Numero visibile (es. "601" come in "S.601") |
| `fase` | str | Stringa fase (es. "S.601") |
| `ramo_origine` | str | "S" = Senato, "C" = Camera |
| `titolo` | str | Titolo del DDL |
| `data_presentazione` | str | Data presentazione (ISO 8601) |
| `stato_ddl` | str | Stato iter (es. "Approvato") |
| `data_stato_ddl` | str | Data stato (ISO 8601) |
| `presentato_trasmesso` | str | Flag presentato/trasmesso |
| `natura` | str | Natura (es. "DDL", "DL", "DDLC") |
| `descr_iniziativa` | str | Descrizione iniziativa legislativa |
| `urn_testo_presentato` | str | NIR URN del testo presentato (solo ramo=S); formato `urn:nir:senato.repubblica:disegno.legge:{N}.legislatura;{num}` |
| `has_testo_presentato` | bool | True se URN disponibile |
| `urn_testo_approvato` | str | NIR URN del testo approvato in quella fase (copertura 2.6–7.9% per legislatura) |
| `has_testo_approvato` | bool | True se URN approvato disponibile |
| `n_emendamenti` | int | Numero emendamenti totali |
| `n_emendamenti_akn` | int | Numero emendamenti con testo AKN disponibile |
| `has_emendamenti` | bool | True se `n_emendamenti > 0` |
| `has_emendamenti_akn` | bool | True se `n_emendamenti_akn > 0` |
| `fonte` | str | "sparql:dati.senato.it" |
| `data_fetch` | str | Timestamp fetch (ISO 8601 UTC) |

---

## 9.2 Schema colonne — `atti_camera.parquet`

Prodotto da `fetch_metadati_camera.py`. Tutte le colonne derivate con `COUNT` sono già corrette per la duplicazione triplestore (divise per 2 in Python).

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_atto` | str | ID atto (last segment URI: `attocamera.rdf/ac{leg}_{n}`) |
| `id_numerico` | int | `dc:identifier` — intero, chiave keyset pagination |
| `legislatura` | int | Numero legislatura (13–19) |
| `titolo` | str | `dc:title` — titolo esteso dell'atto |
| `data_presentazione` | str | Data ISO 8601 (`dc:date` della versioneTestoAtto con MIN data) |
| `tipo_atto` | str | `dc:type` — es. "Progetto di Legge" |
| `natura` | str | `ocd:rif_natura → rdfs:label` — es. "Proposta di legge ordinaria" |
| `iniziativa` | str | `ocd:iniziativa` — "Parlamentare", "Governativa", "Popolare" |
| `stato_iter` | str | `rdfs:label` dello statoIter con MAX(dc:date) |
| `data_stato_iter` | str | `dc:date` dello statoIter con MAX(dc:date), ISO 8601 |
| `n_stati_iter` | int | COUNT(DISTINCT ocd:rif_statoIter) / 2 |
| `url_testo_presentato` | str | `dcterms:isReferencedBy` della versioneTestoAtto con MIN(dc:date) |
| `has_testo` | bool | True se url_testo_presentato non è null |
| `n_versioni_testo` | int | COUNT(DISTINCT ocd:rif_versioneTestoAtto) / 2 |
| `primo_firmatario_id` | str | Last segment URI di `ocd:primo_firmatario` (es. `d306026_17`) |
| `has_trasmissione` | bool | True se `ocd:rif_trasmissione` esiste (navetta al Senato) |
| `n_abbinamenti` | int | COUNT(DISTINCT ocd:rif_abbinamento) / 2 |
| `url_scheda_camera` | str | `dcterms:isReferencedBy` sull'atto (URL scheda sito Camera) |
| `fonte` | str | `"sparql:dati.camera.it"` |
| `data_fetch` | str | Timestamp fetch (ISO 8601 UTC) |

---

## 10. Bug noti e workaround

| Bug | Causa | Fix/Workaround |
|---|---|---|
| `n_emendamenti_akn = 0` nonostante 552 righe | `parse_counts()` usava sempre `val(r, "n_emend")` ma la query AKN usa alias `?n_emend_akn` | **Fixato** in `fetch_metadati_senato.py`: `parse_counts()` ora accetta parametro `sparql_var` |
| HTTP 400 su GROUP BY con `osr:FaseIter` | Endpoint SPARQL Senato non supporta GROUP BY + HAVING su questa classe | Usare query senza HAVING; esplorare con dump_props() su campioni |
| `osr:Ddl` query → 0 righe | `osr:numero` usato come required triple ma non esiste | Rimuovere `osr:numero`; usare `osr:numeroFase` come OPTIONAL |
| Emendamenti Camera — HTTP 403 | Il server Camera richiede header `Referer` | **Fixato**: aggiungere `Referer: http://documenti.camera.it/` alla richiesta su `getDocumento.ashx`. Confermato funzionante (2026-05-27). Una riga di codice. |
| `atti_senato.parquet` non leggibile da pandas/pyarrow di sistema | pyarrow 24 (usato da `uv`) scrive Parquet formato 2.6 di default; pyarrow 19 (sistema) supporta max 2.4. `version='2.4'` passato a `to_parquet()` è ignorato silenziosamente da pyarrow 24. Diagnostica: `pq.read_metadata()` mostra `format_version: 2.6` | **Fixato** in `fetch_metadati_senato.py`: scrittura tramite DuckDB COPY TO (`write_parquet()` helper) che produce formato 1.0, compatibile con tutti i reader. Regola generale: usare DuckDB COPY TO in tutti gli script che scrivono Parquet. |
| Endpoint Senato HTTP 403 su tutte le legislature | Rate limiting o blocco temporaneo IP dell'endpoint `dati.senato.it`. Si manifesta dopo fetch intensivi ravvicinati (più run in sequenza). | Attendere almeno 15–30 minuti prima di ritentare. Verificare con `curl -I https://dati.senato.it/sparql` se il blocco è ancora attivo. |
| Triplestore Camera — triple RDF duplicate | Ogni istanza di `ocd:atto` ha `rdf:type ocd:atto` e `ocd:rif_leg` presenti **due volte** nel grafo. Effetto: `COUNT(*)` su pattern `?atto a ocd:atto` restituisce il doppio del numero reale; le query con `ORDER BY` restituiscono lo stesso atto due volte in sequenza. Confermato empiricamente (2026-05-28): Leg17 `COUNT(*)`=9.806, `COUNT(DISTINCT ?atto)`=4.903. | Usare **sempre** `SELECT DISTINCT ?atto` e `COUNT(DISTINCT ?atto)` nelle query Camera. Per i COUNT di proprietà multi-valued (statoIter, versioneTestoAtto) dividere per 2 in Python dopo l'aggregazione. |
| Camera — `dc:identifier` non-intero: atti navetta esclusi dalla keyset intera | `FILTER(xsd:integer(?id) > N)` esclude silenziosamente gli atti con `dc:identifier` non-intero (navette e varianti: "105-B", "1061-bis", "244-quinquies", ecc.). Leg13: ~1.199 atti esclusi (14.5% del totale). Confermato (2026-05-28). | **Fixato** in `fetch_metadati_camera.py`: keyset su `FILTER(STR(?atto) > "{last_atto}") ORDER BY STR(?atto)`. Ordinamento lessicografico sugli URI, totale e senza buchi. Recupero verificato: Leg13 = 8.281 atti confermati. |
| Camera — HTTP 400 su VALUES blocks di Query B/C/D | Virtuoso Camera risponde HTTP 400 su alcune chiamate POST con VALUES block di ~500 URI (payload ~35KB). Si manifesta su Leg15 pag.1 e Leg16 pag.6-7 e 10-11 durante `fetch_metadati_camera.py`. Causa probabile: limite query size lato server (~10-15KB threshold). | Per Leg13-15 il problema è irrilevante (0% copertura natura/statoIter/vta genuina — pre-digitale). Per Leg16 causa ~1.000 atti con natura=null (copertura 82.8% invece del 100% reale). **Fix da implementare (T2-fix)**: chunking delle liste `atti_uris` in sotto-batch da **100 URI** prima di costruire il VALUES block nelle Query B, C, D. Esempio: `for chunk in [uris[i:i+100] for i in range(0, len(uris), 100)]: run_query(chunk)`. Poi merge dei risultati in Python prima del join. Leg16 va rifetchata con `--force` dopo il fix. |

---

## 11. Dipendenze

Il progetto usa `uv` per la gestione delle dipendenze. Configurate in `pyproject.toml`.

Principali: `pandas`, `pyarrow`, `requests`, `duckdb`.

**Nota**: in ambienti senza `duckdb`, `fetch_metadati_senato.py` cade automaticamente su CSV (flag `HAS_PARQUET`). `pyarrow` non è più richiesta per la scrittura Parquet — si usa DuckDB COPY TO.

---

## 12. Convenzioni di codice

- Tutti gli script usano `# /// script` header per `uv run` (inline dependencies).
- Tutti gli script accettano argomenti CLI via `argparse`; documentati nel docstring.
- Ogni script ha un flag `--dry-run` che stampa le query senza eseguirle.
- Nomi script: `fetch_` = scarica dati, `build_` = costruisce tabelle derivate, `diag_` = diagnostica (va in `explo_script/`).
- Sleep tra chiamate SPARQL: 1 secondo (rispettare rate limiting).
- Retry automatico: 3 tentativi con 5 secondi di attesa.
- Logging: ogni script di produzione scrive un `.json` di log in `data/meta/`.

---

## 13. Convenzioni di commento del codice

Tutti gli script di produzione devono essere commentati **in inglese**, con stile preciso e riprodubile. L'obiettivo è consentire a un ricercatore esterno — che non ha partecipato allo sviluppo — di comprendere ogni scelta tecnica senza consultare documentazione esterna.

### Cosa commentare obbligatoriamente

- **Intestazione di script** (docstring top-level): scopo analitico, fonti dati, limitazioni note, formato di output atteso, flag CLI disponibili. La versione bilingue (IT + EN) è accettata solo qui, per facilitare il collaboratore.
- **Query SPARQL**: annotare la proprietà o la catena di proprietà usata; citare esplicitamente le scoperte diagnostiche rilevanti, con data ISO 8601. Esempio:
  ```python
  # osr:numero does not exist on osr:Ddl — use osr:numeroFase (confirmed 2026-05-27)
  ```
- **Parametri tecnici non ovvi**: magic numbers, soglie, chunk size di paginazione — spiegare il valore e la sua origine (es. limite imposto dall'endpoint, osservazione empirica).
- **Workaround tecnici**: ogni deviazione dal codice "ovvio" deve citare la causa specifica. Esempio:
  ```python
  # GROUP BY on osr:FaseIter returns HTTP 400 from the endpoint — iterate without HAVING
  ```
- **Flag e colonne derivate con logica non banale**: documentare l'invariante. Esempio:
  ```python
  # is_prima_fase = (progressivo_iter == 1): only phase 1 holds the original presentation text
  ```
- **Scrittura Parquet**: usare sempre DuckDB COPY TO (non `pandas.to_parquet()`). Commentare il motivo. Esempio:
  ```python
  # DuckDB COPY TO writes Parquet format 1.0, readable by all pyarrow versions;
  # pandas.to_parquet() with pyarrow >= 23 silently defaults to format 2.6 (confirmed 2026-05-27).
  ```

### Cosa NON commentare

- Codice auto-esplicativo: nomi di variabili chiari, operazioni standard di pandas/DuckDB/requests.
- La sequenza operativa ovvia ("now we loop", "open the file", ecc.).
- Informazioni già documentate nel docstring della stessa funzione o in AGENTS.md.

### Stile

- Tono neutro e impersonale, come in un articolo scientifico: "Returns…", "Filters…", "The endpoint requires…".
- Nessun commento in italiano negli script (eccetto il docstring top-level, vedi sopra).
- Date nei commenti in formato ISO 8601 (`YYYY-MM-DD`).
- I commenti su riga singola precedono la riga di codice a cui si riferiscono, non la seguono.
