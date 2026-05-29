# claude_T_camera_v2.md — fetch_metadati_camera_v2.py
# Aggiunta: cofirmatari, dimensione temporale stati iter

## Obiettivo

Creare `script_prova/fetch_metadati_camera_v2.py` come estensione di `fetch_metadati_camera.py`.
Aggiunge per ogni atto Camera:
- Lista cofirmatari (`ocd:altro_firmatario`)
- Storico completo stati iter con date
- URI completo del primo firmatario (già parzialmente presente)

## ONTOLOGIA DI RIFERIMENTO OBBLIGATORIA

Leggere prima di scrivere qualsiasi query:
`/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/Ontologia_camera.md`

---

## Firmatari Camera (dall'ontologia ufficiale Camera OWL)

### Primo firmatario

```sparql
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?atto ?dep ?nome ?cognome WHERE {
  ?atto ocd:primo_firmatario ?dep .
  OPTIONAL { ?dep foaf:firstName ?nome    }
  OPTIONAL { ?dep foaf:surname  ?cognome  }
}
```

- `ocd:primo_firmatario`: domain `ocd:atto | ocd:DOC | ocd:aic`, range `ocd:deputato | ocd:membroGoverno`
- URI deputato: `http://dati.camera.it/ocd/deputato.rdf/d{id}_{leg}`
- Copertura: ~98% in Leg17, ~90% in Leg13-15

### Cofirmatari

```sparql
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT ?atto ?dep WHERE {
  ?atto ocd:altro_firmatario ?dep .
}
```

- `ocd:altro_firmatario`: domain `ocd:atto | ocd:aic`, range `ocd:deputato | ocd:membroGoverno`
- Copertura: ~62% (da `dc:contributor` in schema attuale) — da verificare con `ocd:altro_firmatario`

### Gruppo deputato Camera

Il collegamento deputato → gruppo per la Camera usa `ocd:` propri — **NON `osr:`**.
La struttura è diversa dal Senato. Confermato empiricamente 2026-05-29.

```sparql
PREFIX ocd:     <http://dati.camera.it/ocd/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>

?dep ocd:aderisce ?adG .
?adG ocd:rif_gruppoParlamentare ?gruppoURI ;
     ocd:startDate ?adG_start .          # YYYYMMDD — per dedup su cambio gruppo
OPTIONAL { ?adG ocd:endDate ?adG_end . }
OPTIONAL { ?adG rdfs:label  ?gruppo_nome . }   # "PARTITO DEMOCRATICO (19.03.2013-22.03.2018)"
?gruppoURI ocd:rif_leg <{leg_uri}> .           # filtra per legislatura
OPTIONAL { ?gruppoURI dcterms:alternative ?gruppo_sigla . }  # "PD"
```

Proprietà confermate:
- `ocd:aderisce`: domain `ocd:deputato`, range `ocd:adesioneGruppo` (blank node)
- `ocd:rif_gruppoParlamentare`: blank node → URI gruppo (es. `gruppoParlamentare.rdf/gr1611`)
- `ocd:startDate` / `ocd:endDate`: date adesione YYYYMMDD
- `rdfs:label` su adesioneGruppo: nome + periodo (es. "PARTITO DEMOCRATICO (19.03.2013-22.03.2018)")
- `ocd:rif_leg` su gruppoParlamentare: URI legislatura (filtra al gruppo giusto)
- `dcterms:alternative` su gruppoParlamentare: sigla (es. "PD")

**Cosa NON funziona** (restituisce 0 risultati): `osr:legislatura`, `osr:gruppo`,
`osr:inizio`, `osr:fine`, `osr:denominazione` — sono predicati Senato, non Camera.

Deduplicazione se deputato cambia gruppo: `ORDER BY adG_start DESC`, `DROP_DUPLICATES` su `uri_deputato`.

---

## Dimensione temporale — stati iter

`ocd:rif_statoIter` è multivalore (avg 6.4 per atto in Leg17). Lo storico completo dà la timeline:

```sparql
SELECT ?atto ?stato ?label ?data WHERE {
  ?atto ocd:rif_statoIter ?stato .
  ?stato rdfs:label ?label ;
         dc:date    ?data .
}
ORDER BY ?atto ?data
```

Valori `rdfs:label` rilevanti per analisi:
- `"Da assegnare"` → data presentazione effettiva
- `"Approvato definitivamente. Legge"` → DDL approvato
- `"Ritirato"`, `"Assorbito dall'approvazione di pdl abbinato"` → DDL concluso senza approvazione

---

## Copertura per legislatura — confermata (2026-05-29, fetch_metadati_camera_v2.py)

| Leg | n_atti | primo_firmatario | altro_firmatario | rif_statoIter (assegnazione) | rif_statoIter (approvazione) | gruppi |
|---|---|---|---|---|---|---|
| 13 | 8.281 | 90.2% ✅ | 45.9% ✅ | **0%** ✅ (pre-digitale) | **0%** ✅ | 100% ✅ (639 dep.) |
| 14 | 7.176 | 90.1% ✅ | 47.1% ✅ | **0%** ✅ (pre-digitale) | **0%** ✅ | 94.9% ✅ (616/649) |
| 15 | 3.620 | **98.8%** ✅ | 54.8% ✅ | **0%** ✅ (pre-digitale) | **0%** ✅ | 95.3% ✅ (622/653) |
| 16 | 5.820 | 97.7% ✅ | **69.2%** ✅ | **0%** ✅ (17 atti con stati ≠ "Da assegnare") | **0%** ✅ | 100% ✅ (666 dep.) |
| 17 | 4.903 | 97.1% ✅ | 61.2% ✅ | 100% ✅ | 3.9% ✅ (190 DDL) | 97.0% ✅ |
| 18 | 3.757 | 95.6% ✅ | 59.0% ✅ | 100% ✅ | 3.9% ✅ (145 DDL) | 100% ✅ (651 dep.) |
| 19 | 2.965 | 93.5% ✅ | 57.4% ✅ | 100% ✅ | 5.5% ✅ (162 DDL) | 100% ✅ (405 dep.) |

**Totale Leg13–19**: 36.522 atti in `atti_camera_v2.parquet`, 279.769 righe in `cofirmatari_camera.parquet`.

Note anomalie:
- **Leg15** primo_firmatario 98.8%: superiore alle attese (~90%) — confermato, non artefatto.
- **Leg16** altro_firmatario 69.2%: picco anomalo (vs. 45–61% nelle altre legislature).
- **Leg14–15** gruppi <100%: la quota residua sono `ocd:membroGoverno` (blank node, senza `ocd:aderisce`).
- **Leg16** data_assegnazione 0%: i 17 atti con `ocd:rif_statoIter` hanno label diversa da "Da assegnare".

## Attenzione: triple duplicate Camera

Il triplestore Camera ha ogni istanza duplicata. Usare SEMPRE `SELECT DISTINCT` e `COUNT(DISTINCT ...)`. Per i COUNT multivalore dividere per 2 in Python.

---

## Schema output

### File principale: `data/meta/atti_camera_v2.parquet`

Tutte le colonne di `atti_camera.parquet` più:

| Colonna | Tipo | Descrizione |
|---|---|---|
| `primo_firmatario_uri` | str | URI completo deputato primo firmatario |
| `primo_firmatario_nome` | str | `foaf:firstName + foaf:surname` |
| `n_cofirmatari` | int | COUNT(DISTINCT ocd:altro_firmatario) / 2 |
| `data_prima_assegnazione` | str | dc:date dello statoIter "Da assegnare" |
| `data_approvazione` | str | dc:date dello statoIter "Approvato definitivamente. Legge" |
| `stato_finale` | str | rdfs:label dello statoIter con MAX(dc:date) (già presente) |

### File secondario: `data/meta/cofirmatari_camera.parquet`

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_atto` | str | ID atto Camera |
| `legislatura` | int | Numero legislatura |
| `uri_deputato` | str | URI deputato cofirmatario |
| `nome_deputato` | str | Nome leggibile |
| `gruppo_uri` | str | URI gruppo parlamentare |
| `gruppo_nome` | str | Nome gruppo |
| `is_primo_firmatario` | bool | True per il primo firmatario |

---

## Convenzioni

- Script in `script_prova/fetch_metadati_camera_v2.py` (NON modificare `fetch_metadati_camera.py`)
- CLI identico a `fetch_metadati_camera.py`: `--legs`, `--force`, `--dry-run`
- Aggiungere flag: `--no-firmatari`
- Stessa strategia keyset URI di `fetch_metadati_camera.py`
- FILTER cursor-range per Query B/C (no VALUES blocks — causano HTTP 400)
- Scrittura Parquet via DuckDB COPY TO
- Commenti in inglese, stile scientifico
