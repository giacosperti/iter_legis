# readme_datasetbuilding.md
# Documentazione tecnica — Dataset iter-legis

Riferimento tecnico completo per la costruzione del dataset della tesi su complessità legislativa e frammentazione politica (legislature 13–19).

---

## 1. Architettura dati — 4 livelli

```
Livello 0 — Raw files
  data/raw/senato/{id_fase}/testo_presentato.pdf
  data/raw/senato/{id_fase}/testo_presentato.pdf.meta.json
  data/raw/senato/{id_fase}/emendamenti/{id_emend}.akn.xml
  data/raw/camera/{id_atto}/testo_presentato.pdf
  data/raw/camera/emendamenti/leg{N}/{id_allegato}.html

Livello 1 — Metadati strutturati (Parquet)
  data/meta/atti_senato.parquet          (T1 — completato)
  data/meta/atti_senato_v2.parquet       (T1v2 — completato)
  data/meta/firmatari_senato.parquet     (T1v2 — completato)
  data/meta/atti_camera.parquet          (T2 — completato)
  data/meta/atti_camera_v2.parquet       (T2v2 — completato)
  data/meta/cofirmatari_camera.parquet   (T2v2 — completato)
  data/meta/t_votazioni.parquet          (T7 — da fare)
  data/meta/t_fasi_iter.parquet          (T7 — da fare)

Livello 2 — Testo estratto
  data/text/{id_fase}/testo_presentato.txt
  data/text/{id_fase}/testo_presentato.extract.json

Livello 3 — Dataset analitico
  data/dataset/iter_legis.duckdb
    ├── t_atti_senato
    ├── t_atti_camera
    ├── t_firmatari_senato
    ├── t_coalizioni
    ├── t_votazioni
    ├── t_fasi_iter
    └── t_testi
```

---

## 2. Stato avanzamento task

### Completati

| Task | Script | Output |
|---|---|---|
| T0 | — | struttura cartelle |
| T1 | `fetch_metadati_senato.py` | `atti_senato.parquet` (58.779 righe Leg13–19) |
| T-Ana | `fetch_anagrafica_sparql.py` | `data/Leg{N}/Anagrafica/senatori_{N}.json` |
| T-Coal | `build_coalizioni.py` | `data/coalizioni_leg13_19.csv` |
| T2 | `fetch_metadati_camera.py` | `atti_camera.parquet` (36.522 righe Leg13–19) |
| T2-fix | `fetch_metadati_camera.py` | Leg16 natura=100%, VALUES→cursor-range |
| T1v2 | `fetch_metadati_senato_v2.py` | `atti_senato_v2.parquet` (8.004 righe Leg17), `firmatari_senato.parquet` (83.064 righe Leg17) |
| T2v2 | `fetch_metadati_camera_v2.py` | `atti_camera_v2.parquet` (36.522 righe Leg13–19), `cofirmatari_camera.parquet` (279.769 righe Leg13–19) |

### Da fare — in ordine di priorità

| Task | Script | Dipendenze |
|---|---|---|
| T3 | `fetch_testi_presentati_senato.py` | T1 |
| T4 | `fetch_testi_presentati_camera.py` | T2 |
| T5 | `fetch_emendamenti_senato.py` | T1 |
| T6 | `fetch_emendamenti_camera.py` | T2 |
| T7 | `build_tabelle_temporali.py` | T1 |
| T8 | `build_dataset_analitico.py` | T1v2, T2v2, T7 |
| T9 | `build_complessita_testuale.py` | T3, T4, T5 |

---

## 3. Schema colonne — atti_senato.parquet

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_fase` | str | ID fase (last segment URI) |
| `id_ddl_interno` | str | `osr:idDdl` — ID DDL complessivo |
| `id_fase_sparql` | str | `osr:idFase` |
| `uri_ddl` | str | URI completo triplestore |
| `legislatura` | int | 13–19 |
| `progressivo_iter` | int | 1 = prima fase |
| `is_prima_fase` | bool | True se progressivo_iter == 1 |
| `numero_fase` | str | Numero visibile (es. "601") |
| `fase` | str | Stringa fase (es. "S.601") |
| `ramo_origine` | str | "S" = Senato, "C" = Camera |
| `titolo` | str | Titolo DDL |
| `data_presentazione` | str | ISO 8601 |
| `stato_ddl` | str | Stato iter |
| `data_stato_ddl` | str | ISO 8601 |
| `presentato_trasmesso` | str | Flag |
| `natura` | str | "DDL", "DL", "DDLC", ecc. |
| `descr_iniziativa` | str | Testo iniziativa |
| `urn_testo_presentato` | str | NIR URN (`urn:nir:senato.repubblica:...`) |
| `has_testo_presentato` | bool | |
| `urn_testo_approvato` | str | NIR URN testo approvato (2.6–7.9%) |
| `has_testo_approvato` | bool | |
| `n_emendamenti` | int | |
| `n_emendamenti_akn` | int | |
| `has_emendamenti` | bool | |
| `has_emendamenti_akn` | bool | |
| `fonte` | str | "sparql:dati.senato.it" |
| `data_fetch` | str | ISO 8601 UTC |

---

## 3.5 Schema colonne — atti_senato_v2.parquet

Tutte le colonne di `atti_senato.parquet` (§3) più:

| Colonna | Tipo | Descrizione |
|---|---|---|
| `uri_primo_firmatario` | str | URI senatore primo firmatario (null se non Parlamentare o no link) |
| `nome_primo_firmatario` | str | `foaf:firstName + foaf:lastName` del primo firmatario |
| `tipo_iniziativa` | str | "Parlamentare", "Governativa", "Regionale", "Popolare", "CNEL" |
| `gruppo_primo_firmatario_uri` | str | URI gruppo parlamentare (es. `http://dati.senato.it/gruppo/73`) |
| `gruppo_primo_firmatario_nome` | str | `osr:titolo` del gruppo (es. "Partito Democratico") |
| `gruppo_primo_firmatario_sigla` | str | `osr:titoloBreve` (es. "PD") |
| `n_cofirmatari` | int | Numero cofirmatari con link `osr:senatore` |
| `n_cofirmatari_totale` | int | Numero totale firmatari (inclusi senza link) |

Copertura Leg17: primo firmatario con URI 82.5% (ramo S), 1.0% (ramo C — atteso).

---

## 3.6 Schema colonne — firmatari_senato.parquet

Una riga per istanza `osr:Iniziativa` (firmatario):

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_fase` | str | ID fase DDL (`osr:idFase`) |
| `legislatura` | int | Numero legislatura |
| `uri_iniziativa` | str | URI istanza `osr:Iniziativa` |
| `is_primo_firmatario` | bool | True se `osr:primoFirmatario = "1"` |
| `uri_senatore` | str | URI senatore (null se non disponibile, ~30% delle righe) |
| `nome_senatore` | str | Nome leggibile (`foaf:firstName+lastName` o `osr:presentatore`) |
| `tipo_iniziativa` | str | Tipo iniziativa |
| `data_firma` | str | `osr:dataAggiuntaFirma` (solo cofirmatari) |
| `data_ritiro_firma` | str | `osr:dataRitiroFirma` |
| `gruppo_uri` | str | URI gruppo parlamentare |
| `gruppo_nome` | str | Nome gruppo |
| `gruppo_sigla` | str | Sigla gruppo |
| `carica_gruppo` | str | `osr:carica` in adesioneGruppo ("Membro", "Presidente", ecc.) |

Risultati Leg17: 83.064 righe; 9.205 primo firmatario, 73.859 cofirmatari; 333 URI senatori unici.

---

## 4. Schema colonne — atti_camera.parquet

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_atto` | str | ID atto (last segment URI) |
| `id_numerico` | int | `dc:identifier` |
| `legislatura` | int | 13–19 |
| `titolo` | str | `dc:title` |
| `data_presentazione` | str | ISO 8601 |
| `tipo_atto` | str | "Progetto di Legge" |
| `natura` | str | `ocd:rif_natura → rdfs:label` |
| `iniziativa` | str | "Parlamentare", "Governativa", "Popolare" |
| `stato_iter` | str | statoIter con MAX(dc:date) |
| `data_stato_iter` | str | ISO 8601 |
| `n_stati_iter` | int | COUNT(DISTINCT)/2 |
| `url_testo_presentato` | str | URL getDocumento.ashx |
| `has_testo` | bool | |
| `n_versioni_testo` | int | COUNT(DISTINCT)/2 |
| `primo_firmatario_id` | str | Last segment URI deputato |
| `has_trasmissione` | bool | Navetta al Senato |
| `n_abbinamenti` | int | COUNT(DISTINCT)/2 |
| `url_scheda_camera` | str | URL scheda Camera |
| `fonte` | str | "sparql:dati.camera.it" |
| `data_fetch` | str | ISO 8601 UTC |

---

## 4.1 Schema colonne — atti_camera_v2.parquet

Tutte le colonne di `atti_camera.parquet` (§4) più:

| Colonna | Tipo | Descrizione |
|---|---|---|
| `primo_firmatario_uri` | str | URI completo `ocd:deputato` del primo firmatario |
| `primo_firmatario_nome` | str | `foaf:firstName + foaf:surname` |
| `n_cofirmatari` | int | Numero cofirmatari (`ocd:altro_firmatario`) |
| `data_prima_assegnazione` | str | ISO 8601 — dc:date dello statoIter con label "Da assegnare" |
| `data_approvazione` | str | ISO 8601 — dc:date dello statoIter "Approvato definitivamente. Legge" (null se non approvato) |

Colonne **rimosse** rispetto a `atti_camera.parquet` (non presenti nel triplestore in forma utile):
`n_stati_iter`, `n_versioni_testo`, `primo_firmatario_id`, `has_trasmissione`, `n_abbinamenti`

Copertura confermata Leg13–19 (2026-05-29):

| Leg | n_atti | primo_firmatario_uri | n_cofirmatari>0 | data_assegnazione | data_approvazione |
|---|---|---|---|---|---|
| 13 | 8.281 | 90.2% | 45.9% | 0% | 0% |
| 14 | 7.176 | 90.1% | 47.1% | 0% | 0% |
| 15 | 3.620 | 98.8% | 54.8% | 0% | 0% |
| 16 | 5.820 | 97.7% | 69.2% | 0% | 0% |
| 17 | 4.903 | 97.1% | 61.2% | 100% | 3.9% |
| 18 | 3.757 | 95.6% | 59.0% | 100% | 3.9% |
| 19 | 2.965 | 93.5% | 57.4% | 100% | 5.5% |

Anomalie notevoli: Leg15 primo_firmatario 98.8% (superiore alle attese); Leg16 altro_firmatario 69.2% (picco anomalo); Leg16 data_assegnazione 0% nonostante 17 atti con `ocd:rif_statoIter` (label diversa da "Da assegnare").

---

## 4.2 Schema colonne — cofirmatari_camera.parquet

Una riga per (atto × firmatario). Include primo firmatario e cofirmatari.

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_atto` | str | ID atto Camera (last segment URI, es. "ac17_1234") |
| `legislatura` | int | Numero legislatura |
| `uri_deputato` | str | URI `ocd:deputato` o blank node per `ocd:membroGoverno` |
| `nome_deputato` | str | `foaf:firstName + foaf:surname` (null per membroGoverno) |
| `is_primo_firmatario` | bool | True per `ocd:primo_firmatario`, False per `ocd:altro_firmatario` |
| `gruppo_uri` | str | URI `ocd:gruppoParlamentare` (null per blank node membroGoverno) |
| `gruppo_nome` | str | `rdfs:label` sull'adesioneGruppo — include periodo, es. "PD (19.03.2013-22.03.2018)" |
| `gruppo_sigla` | str | `dcterms:alternative` su gruppoParlamentare, es. "PD" |
| `data_fetch` | str | ISO 8601 UTC |

Note:
- Copertura gruppi: 97–100% per leg. (Leg14: 94.9%, Leg15: 95.3%, Leg17: 97.0%; resto 100%). Il residuo senza gruppo sono blank node `ocd:membroGoverno` (senza `ocd:aderisce`).
- Risultati Leg13–19: 279.769 righe totali.
- Per i predicati Camera dei gruppi vedere §6.6.

---

## 5. Fatti tecnici triplestore Senato

### 5.1 osr:Ddl — dati empirici Leg13–19

| Leg | Righe totali | DDL unici (idDdl) | ramo=S | ramo=C |
|---|---|---|---|---|
| 13 | 13.318 ✅ | 12.041 | 5.339 | 7.979 |
| 14 | 10.483 ✅ | 9.455 | 3.975 | 6.508 |
| 15 | 5.568 ✅ | 5.395 | 2.056 | 3.512 |
| 16 | 9.572 ✅ | 9.112 | 3.748 | 5.824 |
| 17 | 8.004 ✅ | 7.443 | 3.096 | 4.908 |
| 18 | 6.479 ✅ | 6.059 | 2.719 | 3.760 |
| 19 | 4.913 ✅ | 4.490 | 1.946 | 2.967 |

Leg13, Leg14, Leg16 erano troncate nel fetch originale (cap Virtuoso). Fix: keyset pagination su `osr:idFase`.

### 5.2 Proprietà non esistenti — NON usare

| Proprietà | Motivo |
|---|---|
| `osr:numero` su `osr:Ddl` | Non esiste — usare `osr:numeroFase` |
| `osr:dataPresenta` | Non esiste — usare `osr:dataPresentazione` |
| `osr:legislatura` su `osr:Senatore` | Non esiste — navigare via `osr:Iniziativa` |
| `osr:seduta` su `osr:Emendamento` | Non esiste — solo su Votazione/Intervento |
| `osr:testoUnificato` popolato | COUNT = 0 su Leg13–19 — ignorare |

### 5.3 osr:Emendamento — copertura e qualità

| Leg | Tot. triplestore | Coverage parquet | Note |
|---|---|---|---|
| 13 | 709 | 20% | catena linking spezzata |
| 14 | 86.147 | 90.5% | ~8k orfani |
| 15 | 33.652 | 97.2% | ✅ |
| 16 | 116.909 | 138% | doppio conteggio testi unificati |
| 17 | 253.387 | ~100% | ✅ |
| 18 | 151.262 | 98.2% | ✅ |
| 19 | 53.337 | ~100% | parziale |

Emendamenti orfani (~6–9%): catena `osr:oggetto → osr:relativoA` spezzata, non recuperabili.
Coverage >100% su Leg16: emendamenti collegati a più DDL (testi unificati) → non sommare `n_emendamenti` per totale legislatura; usare COUNT(DISTINCT) SPARQL.

### 5.4 osr:Iniziativa — struttura firmatari (confermata empiricamente)

| Proprietà | Tipo | Note |
|---|---|---|
| `osr:primoFirmatario` | string `"1"` | Flag — NON booleano |
| `osr:senatore` | URI | ~30% delle Iniziativa Parlamentare |
| `osr:presentatore` | string | Nome leggibile — sempre presente |
| `osr:tipoIniziativa` | string | "Parlamentare", "Governativa", "Regionale", "Popolare", "CNEL" |
| `osr:dataAggiuntaFirma` | string | Solo cofirmatari |
| `osr:dataRitiroFirma` | string | Opzionale |

### 5.5 Catena gruppo parlamentare — confermata (2026-05-29)

```
osr:Senatore
  --[ocd:aderisce]-->  [blank node] a ocd:adesioneGruppo
                           ├── osr:legislatura → integer
                           ├── osr:gruppo      → http://dati.senato.it/gruppo/{id}
                           ├── osr:carica      → "Membro" | "Presidente" | ...
                           ├── osr:inizio      → data
                           └── osr:fine        → data (opzionale)
  ocd:gruppoParlamentare
    --[osr:denominazione]--> [blank node] a osr:Denominazione
                                  ├── osr:titolo      → "Partito Democratico"
                                  ├── osr:titoloBreve → "PD"
                                  ├── osr:inizio      → data validità denominazione
                                  └── osr:fine        → data fine validità
```

Fatti chiave:
- `ocd:aderisce` è direttamente sul senatore URI
- Le adesioni sono blank node ma leggibili con SPARQL
- 12.108 istanze di `ocd:adesioneGruppo` nel triplestore Senato
- 188 istanze di `ocd:gruppoParlamentare`
- 15 gruppi distinti in Leg17
- Copertura 100% (333/333 senatori Leg17 via Iniziativa hanno adesioneGruppo)
- Blank node duplicati → necessario DISTINCT su (s, gruppoURI, adGInizio, adGFine)

### 5.6 Pipeline NIR URN testi presentati Senato

```
urn:nir:senato.repubblica:disegno.legge:{N}.legislatura;{numero}
  → GET https://www.senato.it/uri-res/N2Ls?{urn_encoded}
  → HTML → link /service/PDF/PDFServer/BGT/{id}.pdf
  → GET pdf_url → bytes
```

**Uniforme Leg13–19** (confermato empiricamente 2026-05-29 con `strings` su `atti_senato_v2.parquet`).
Prefisso `urn:nir:` (NON `urn:lex:it:`). La proprietà `osr:testoPresentato` contiene sempre un NIR URN — NON un URL diretto AKN XML — in tutte le legislature incluse Leg17–19.

Testo approvato definitivamente (`osr:testoApprovato`): stesso pattern NIR URN con segmento `;approvato` nell'URN (es. `urn:nir:senato.repubblica:disegno.legge;approvato:19.legislatura;998`). Copertura 2.6–7.9% (solo DDL effettivamente approvati come legge).

### 5.9 Schema estrazione testi — quadro completo

| Tipo testo | Legislature | Formato | Metodo |
|---|---|---|---|
| Senato — testo presentato | Leg13–19 | PDF | NIR URN `osr:testoPresentato` → N2Ls → BGT/{id}.pdf |
| Senato — emendamenti | Leg14–19 | AKN XML | `osr:URLTestoXml` su `osr:Emendamento` → download diretto |
| Senato — emendamenti | Leg13 | — | URL in SPARQL presente ma server 404 |
| Camera — testo presentato | Leg13–15 | PDF | `dc:relation` → URL statico `camera.it/_dati/leg{N}/lavori/stampati/pdf/{num}.pdf` |
| Camera — testo presentato | Leg16–19 | PDF | `ocd:rif_versioneTestoAtto` → `getDocumento.ashx` (Referer obbligatorio) |
| Camera — emendamenti | Leg16–19 | HTML | `ocd:allegatoDiscussione → dc:relation` → `getDocumento.ashx` bollettino |
| Camera — emendamenti | Leg13–15 | — | 0 allegati (pre-digitale) |
| Testo approvato definitivamente | Leg13–19 | — | NON disponibile sistematicamente da triplestore — usare normattiva |

### 5.10 Testo approvato definitivamente — perché normattiva

Nessun triplestore (Camera né Senato) espone il testo della legge definitivamente approvata con copertura sistematica:

- **Senato** `osr:testoApprovato`: NIR URN presente, copertura 2.6–7.9% (solo DDL già convertiti in legge). Utilizzabile come check, non come fonte primaria sistematica.
- **Camera** `ocd:approvato`: proprietà booleana su `ocd:votazione` — indica se la votazione era approvativa, NON è un link al testo.
- **Camera** `ocd:rif_versioneTestoAtto`: punta alle versioni del testo presentato/modificato in iter, non necessariamente al testo legge definitivo.

Per ottenere sistematicamente il testo approvato come legge: **normattiva.it** tramite NIR URN della legge (diverso dal NIR URN del DDL). Da implementare in task separato (fuori scope T3–T6).

### 5.7 Encoding emendamenti AKN

| Leg | Encoding |
|---|---|
| Leg14 | UTF-8 con BOM |
| Leg18 | UTF-16 LE |
| Leg19 | ISO-8859-1 |

Usare `chardet` per rilevamento automatico.

### 5.8 Vincoli endpoint Senato — confermati empiricamente (2026-05-29)

| Vincolo | Sintomo | Soluzione |
|---|---|---|
| `VALUES` non supportato (SPARQL 1.0 only) | HTTP 400 Bad Request | Usare `FILTER(?s IN (<u1>, <u2>, ...))` |
| Limite URL ~2100 char | HTTP 403 Forbidden (NON 414) | Ridurre batch o evitare lista URI |
| FILTER IN: soglia empirica 31/32 URI | URL 2063 char → OK; 2119 char → 403 | `URI_BATCH_SIZE = 25` (margine sicuro) |
| FILTER IN inapplicabile a query complesse | Anche 25 URI → 403 per query >300 char | Navigare dalla catena DDL (nessun URI in query) |

Regole operative:
- Non usare mai `VALUES` su questo endpoint
- Per query semplici (corpo ≤ 300 char): `FILTER IN` con max 25 URI
- Per query complesse (corpo > 300 char): navigare da `osr:Ddl → osr:iniziativa → osr:senatore` senza lista URI
- Riferimento implementazione: `script_prova/fetch_metadati_senato_v2.py`

---

## 6. Fatti tecnici triplestore Camera

### 6.1 ocd:atto — dati empirici Leg13–19

| Leg | COUNT(DISTINCT) reale | Note |
|---|---|---|
| 13 | 8.281 | ~14.5% id non-interi |
| 14 | 7.180 | ~1% id non-interi |
| 15 | 3.618 | |
| 16 | 5.817 | |
| 17 | 4.903 | |
| 18 | 3.757 | |
| 19 | 2.965 | |

Triple duplicate: ogni istanza appare 2× → SEMPRE `SELECT DISTINCT` e `COUNT(DISTINCT)`.

### 6.2 Copertura linked entities per legislatura Camera

| Proprietà | Leg13 | Leg14 | Leg15 | Leg16 | Leg17 | Leg18 | Leg19 |
|---|---|---|---|---|---|---|---|
| `dc:title`, `dc:date` | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `ocd:primo_firmatario` (URI) | 90.2% ✅ | 90.1% ✅ | **98.8%** ✅ | 97.7% ✅ | 97.1% ✅ | 95.6% ✅ | 93.5% ✅ |
| `ocd:altro_firmatario` (≥1) | 45.9% ✅ | 47.1% ✅ | 54.8% ✅ | **69.2%** ✅ | 61.2% ✅ | 59.0% ✅ | 57.4% ✅ |
| `ocd:rif_natura` | **0%** | **0%** | **0%** | 100% | 100% | 100% | 100% |
| `ocd:rif_statoIter` (qualsiasi) | **0%** | **0%** | **0%** | **0.3%** | 100% | 100% | 100% |
| `ocd:rif_statoIter` "Da assegnare" | **0%** ✅ | **0%** ✅ | **0%** ✅ | **0%** ✅ | 100% ✅ | 100% ✅ | 100% ✅ |
| `ocd:rif_statoIter` "Approvato" | **0%** ✅ | **0%** ✅ | **0%** ✅ | **0%** ✅ | 3.9% ✅ | 3.9% ✅ | 5.5% ✅ |
| `ocd:rif_versioneTestoAtto` | **0%** | **0%** | **0%** | **0.1%** | ~99% | 98.2% | 89.5% |
| `dc:relation` (PDF diretto) | ~90% | — | — | — | — | — | — |
| gruppi parlamentari (via aderisce) | 100% ✅ | 94.9% ✅ | 95.3% ✅ | 100% ✅ | 97.0% ✅ | 100% ✅ | 100% ✅ |

✅ = confermato empiricamente con `fetch_metadati_camera_v2.py` (2026-05-29), run completo Leg13–19.
Leg13–15 dati pre-digitale genuinamente assenti. Leg16 data_assegnazione=0%: i 17 atti con stati hanno label diversa da "Da assegnare". Leg14–15 gruppi <100%: residuo sono `ocd:membroGoverno` (blank node senza `ocd:aderisce`).

### 6.3 Proprietà Camera — distinzione ontologia vs. triplestore

#### Non usare su ocd:atto (0 risultati empirici, non definite per questo domain)

`ocd:titolo`, `ocd:numero`, `ocd:dataPresentazione`, `ocd:rif_tipoAtto`, `ocd:rif_iter`

#### ocd:ramo — esiste nell'ontologia ma domain sbagliato per ocd:atto

`ocd:ramo` è una `owl:DatatypeProperty` con **domain = `ocd:aic`** (atto di indirizzo e controllo), NON `ocd:atto`. È corretto che restituisca 0 risultati nelle query su `ocd:atto`. Non è una proprietà da usare per le proposte di legge.

#### ocd:ac — definita nell'ontologia, NON popolata nel triplestore

`ocd:ac` è una `owl:ObjectProperty` con domain `ocd:atto` (label: "URL dell'atto camera"). Verificata empiricamente con `diag_ocdac_camera.py` (2026-05-29): **0 risultati su qualunque subject** — la proprietà non è usata nel triplestore Camera indipendentemente dal tipo di soggetto. Non inserire nelle query.

### 6.4 dc:relation ≠ URL testo atto

`dc:relation` su `ocd:atto` aggrega i PDF di tutti gli atti abbinati in discussione congiunta — NON è l'URL del testo dell'atto specifico.

Pipeline corretta per il testo:
```
ocd:atto → ocd:rif_versioneTestoAtto (MIN dc:date) → dcterms:isReferencedBy → URL
```

### 6.5 URI legislatura Camera

```
CORRETTO:  http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}
SBAGLIATO: http://dati.camera.it/ocd/legislatura/{N}   → 0 risultati
```

Il triplestore Camera include anche legislature del **Regno d'Italia** (pattern `regno_{N}`). Filtrare sempre su `repubblica_{N}`.

### 6.6 Catena gruppo parlamentare Camera — confermata empiricamente (2026-05-29)

La Camera usa predicati `ocd:` propri — **struttura diversa dal Senato** (§5.5), che usa `osr:`.

```
ocd:deputato
  --[ocd:aderisce]--> [blank node] a ocd:adesioneGruppo
                           ├── ocd:rif_gruppoParlamentare → ocd:gruppoParlamentare URI
                           ├── ocd:startDate              → "YYYYMMDD"
                           ├── ocd:endDate                → "YYYYMMDD" (opzionale)
                           └── rdfs:label                 → "PARTITO DEMOCRATICO (19.03.2013-22.03.2018)"
  ocd:gruppoParlamentare
       ├── ocd:rif_leg          → <legislatura.rdf/repubblica_{N}>   ← usare per filtrare
       ├── dc:title             → "PARTITO DEMOCRATICO (PD) (19.03.2013"  (include data, truncato)
       └── dcterms:alternative  → "PD"   ← sigla pulita
```

Fatti chiave:
- `rdfs:label` sull'**adesioneGruppo** (blank node) = nome leggibile con periodo — più affidabile di `dc:title` sul gruppo (che appare troncato).
- Il filtro per legislatura va posto su `?gruppoURI ocd:rif_leg <{leg_uri}>`, non sul blank node.
- Deputati che cambiano gruppo nella stessa legislatura hanno più adesioneGruppo; tenere quello con `ocd:startDate` più recente.
- Blank node `nodeID://...` da `ocd:membroGoverno` non hanno `ocd:aderisce` → escluderli prima della batch.
- **NON funziona**: `osr:legislatura`, `osr:gruppo`, `osr:inizio`, `osr:fine`, `osr:denominazione` → 0 risultati.

---

## 7. Bug noti e workaround

| Bug | Causa | Fix/Workaround |
|---|---|---|
| `n_emendamenti_akn = 0` nonostante dati presenti | `parse_counts()` usava alias SPARQL sbagliato | Fixato in `fetch_metadati_senato.py`: `sparql_var` parameter |
| HTTP 400 su GROUP BY con `osr:FaseIter` | Endpoint Senato non supporta questa combinazione | Usare query senza HAVING |
| `osr:Ddl` query → 0 righe | `osr:numero` usato ma non esiste | Usare `osr:numeroFase` |
| HTTP 403 endpoint Camera | Manca `Referer` header | Aggiungere `Referer: http://documenti.camera.it/` |
| `atti_senato.parquet` illeggibile da pyarrow vecchio | pyarrow 24 scrive Parquet 2.6 di default | DuckDB COPY TO (format 1.0) — regola universale |
| HTTP 403 endpoint Senato dopo fetch intensivi | Rate limiting / blocco temporaneo IP | Attendere 15–30 minuti |
| Triple duplicate Camera | Ogni istanza `ocd:atto` appare 2× nel grafo | SEMPRE `SELECT DISTINCT` e `COUNT(DISTINCT)` |
| Atti Camera con `dc:identifier` non-intero esclusi | Keyset `xsd:integer(?id)` filtra silenziosamente "105-B" ecc. | Keyset su `STR(?atto)` (URI) |
| HTTP 400 su VALUES blocks Camera | Query cost estimator Virtuoso Camera | Sostituire VALUES con FILTER cursor-range |
| `osr:legislatura` su `osr:Senatore` → 0 risultati | La proprietà non è nel domain di `osr:Senatore` | Navigare via `osr:Ddl → osr:iniziativa → osr:senatore` |
| Blank node duplicati adesioneGruppo | Triplestore Senato ha blank node duplicati | DISTINCT su (senatore, gruppoURI, adGInizio, adGFine) |
| `VALUES` → HTTP 400 endpoint Senato | Endpoint Virtuoso Senato non supporta SPARQL 1.1 | Sostituire con `FILTER(?s IN (...))` (vedi §5.8) |
| FILTER IN → HTTP 403 endpoint Senato | URL totale supera ~2100 char; endpoint ritorna 403 non 414 | `URI_BATCH_SIZE = 25`; per query complesse: navigazione DDL |
| GRUPPI_QUERY → HTTP 403 con qualsiasi batch | Corpo query ~500 char → anche 25 URI superano limite URL | Navigare da DDL senza lista URI (LIMIT/OFFSET); vedi §5.8 |
| Query gruppi Camera con predicati `osr:` → 0 risultati | Camera non usa `osr:` per gruppi — usa `ocd:rif_gruppoParlamentare`, `ocd:startDate`, `dcterms:alternative` (confermato 2026-05-29) | Usare predicati corretti, vedi §6.6 |

---

## 8. Usabilità per l'analisi della tesi

| Variabile | Leg13-15 | Leg16 | Leg17-19 |
|---|---|---|---|
| Testo PDF dal Senato | ✅ ramo=S | ✅ ramo=S | ✅ ramo=S |
| Testo PDF dalla Camera | ✅ (dc:relation ~90%) | ✅ | ✅ |
| Durata iter (date) | ❌ | ❌ (0.3%) | ✅ |
| Status approvazione | ❌ | ❌ | ✅ |
| Tipo atto (PDL/DDL) | ❌ + ~10% "Relazione" | ✅ | ✅ |
| Firmatari (Senato) | ✅ (~30% con senatore) | ✅ | ✅ |
| Gruppo parlamentare (Senato) | ✅ | ✅ | ✅ |
| Firmatari (Camera) | ✅ 90% (Leg13-14), 99% (Leg15) | ✅ 97.7% | ✅ 94–97% |
| Cofirmatari Camera (lista) | ✅ 46–55% | ✅ 69.2% | ✅ 57–61% |
| Gruppo parlamentare (Camera) | ✅ 95–100% | ✅ 100% | ✅ 97–100% |
| Emendamenti testo AKN | ✅ 20% | ✅ ~90% | ✅ ~100% |
| Linkage frammentazione | ✅ | ✅ | ✅ |

**Raccomandazione**: l'analisi multivariata principale (complessità + iter + approvazione) deve usare Leg17–19. Leg16 contribuisce se non richiede iter completo. Leg13–15 per statistiche descrittive e testi.

---

## Registro revisioni

| Data | Motivo |
|---|---|
| 2026-05-29 | Prima stesura completa |
| 2026-05-29 | Aggiunti §3.5, §3.6 (schemi v2), §5.8 (vincoli endpoint Senato), nuove righe §7 (T1v2); T1v2 marcato completato |
| 2026-05-29 | Aggiunti §4.1, §4.2 (schemi Camera v2), §6.6 (catena gruppi Camera); aggiornati §2, §6.2, §7, §8 con dati confermati Leg17 T2v2 |
| 2026-05-29 | Run completo Leg13–19 T2v2: aggiornati §2, §4.1, §4.2, §6.2, §8 con coverage confermata per tutte le legislature (36.522 atti, 279.769 firmatari) |
