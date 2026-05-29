# Prompt — fetch_metadati_camera_v2.py

## Contesto operativo

Leggi prima, nell'ordine:
1. `iter-legis/CLAUDE.md` — regole universali del progetto
2. `iter-legis/claudesss/claude_T_camera_v2.md` — specifiche complete di questo task
3. `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/Ontologia_camera.md` — ontologia Camera (obbligatorio prima di scrivere query SPARQL)
4. `iter-legis/script_prova/fetch_metadati_camera.py` — script base di cui questo è l'estensione

## Task

Crea `script_prova/fetch_metadati_camera_v2.py`. NON modificare `fetch_metadati_camera.py`.

Aggiunge al fetch atti Camera (Leg13–19):
- Cofirmatari per atto (`ocd:altro_firmatario`) con nome deputato
- Gruppo parlamentare per primo firmatario e cofirmatari
- Storico stati iter con date complete (non solo lo stato finale)

---

## Fatti tecnici critici — leggere con attenzione

### Firmatari Camera (dall'ontologia Camera OWL ufficiale)

```sparql
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

# Primo firmatario
?atto ocd:primo_firmatario ?dep .
OPTIONAL { ?dep foaf:firstName ?nome    }
OPTIONAL { ?dep foaf:surname   ?cognome }

# Cofirmatari
?atto ocd:altro_firmatario ?dep_co .
OPTIONAL { ?dep_co foaf:firstName ?nome_co    }
OPTIONAL { ?dep_co foaf:surname   ?cognome_co }
```

Proprietà dall'ontologia Camera OWL:
- `ocd:primo_firmatario`: domain=`ocd:atto|ocd:DOC|ocd:aic`, range=`ocd:deputato|ocd:membroGoverno`
- `ocd:altro_firmatario`: domain=`ocd:atto|ocd:aic`, range=`ocd:deputato|ocd:membroGoverno`

URI deputato: `http://dati.camera.it/ocd/deputato.rdf/d{id}_{leg}`

### Gruppo deputato Camera

**ATTENZIONE**: la Camera usa predicati `ocd:` propri — **NON `osr:`** come il Senato.
Confermato empiricamente 2026-05-29. La query con `osr:` restituisce 0 risultati.

```sparql
PREFIX ocd:     <http://dati.camera.it/ocd/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?dep ?gruppoURI ?gruppo_nome ?gruppo_sigla ?adG_start WHERE {
  VALUES ?dep { {dep_uris} }
  ?dep ocd:aderisce ?adG .
  ?adG ocd:rif_gruppoParlamentare ?gruppoURI ;
       ocd:startDate ?adG_start .
  ?gruppoURI ocd:rif_leg <{leg_uri}> .
  OPTIONAL { ?adG       rdfs:label           ?gruppo_nome  . }
  OPTIONAL { ?gruppoURI dcterms:alternative   ?gruppo_sigla . }
}
```

Proprietà chiave:
- `ocd:rif_gruppoParlamentare`: blank node adesioneGruppo → URI gruppo
- `ocd:startDate` / `ocd:endDate`: date adesione YYYYMMDD
- `rdfs:label` su adesioneGruppo: nome + periodo (es. "PARTITO DEMOCRATICO (19.03.2013-22.03.2018)")
- `ocd:rif_leg` su gruppoParlamentare: filtra per legislatura (usa URI piena, non numero)
- `dcterms:alternative` su gruppoParlamentare: sigla (es. "PD")

Dedup se deputato cambia gruppo: tieni il record con `adG_start` più recente.
Filtra URI blank node (`nodeID://`) prima di inviare la batch: membroGoverno non ha gruppi.

### Triple duplicate Camera — regola fondamentale

Il triplestore Camera ha ogni istanza duplicata. SEMPRE:
```sparql
SELECT DISTINCT ?atto ...
COUNT(DISTINCT ?atto)
```
Per COUNT multivalore (statoIter, versioneTestoAtto): dividere per 2 in Python dopo l'aggregazione.

### Keyset pagination — usare URI, non dc:identifier

```sparql
FILTER(STR(?atto) > "{last_atto}") ORDER BY STR(?atto) LIMIT 500
```
NON usare `FILTER(xsd:integer(?id) > N)` — esclude silenziosamente atti con ID non-intero (navette: "105-B", "1061-bis"). Leg13 ha ~14.5% di atti non-interi.

### No VALUES blocks nelle query paginate

VALUES blocks in query B/C → HTTP 400 su Virtuoso Camera (confermato su Leg16).
Usare invece FILTER cursor-range:
```sparql
FILTER(STR(?atto) > "{cursor_start}" && STR(?atto) <= "{cursor_end}")
```

### URI legislatura Camera

```sparql
# CORRETTO:
FILTER(?leg_uri = <http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}>)

# SBAGLIATO — 0 risultati:
FILTER(?leg_uri = <http://dati.camera.it/ocd/legislatura/{N}>)
```

### Copertura per legislatura — confermata Leg13–19 (2026-05-29)

| Leg | n_atti | primo_firmatario | altro_firmatario | data_assegnazione | data_approvazione | gruppi |
|---|---|---|---|---|---|---|
| 13 | 8.281 | 90.2% | 45.9% | 0% (pre-digitale) | 0% | 100% |
| 14 | 7.176 | 90.1% | 47.1% | 0% (pre-digitale) | 0% | 94.9% |
| 15 | 3.620 | 98.8% | 54.8% | 0% (pre-digitale) | 0% | 95.3% |
| 16 | 5.820 | 97.7% | 69.2% | 0% (17 atti con altri stati) | 0% | 100% |
| 17 | 4.903 | 97.1% | 61.2% | 100% | 3.9% | 97.0% |
| 18 | 3.757 | 95.6% | 59.0% | 100% | 3.9% | 100% |
| 19 | 2.965 | 93.5% | 57.4% | 100% | 5.5% | 100% |

Totale: 36.522 atti, 279.769 righe firmatari. Leg13-15 senza statoIter: normale, non è un bug.

---

## Struttura codice da seguire

Stessa architettura di `fetch_metadati_camera.py`:

```
sparql_camera(query) → list[dict]
val(binding, key) → str | None
write_parquet(df, path) → None    # DuckDB COPY TO

# Query
ATTO_QUERY            → invariata (keyset URI, SELECT DISTINCT)
FIRMATARI_QUERY       → nuova (ocd:primo_firmatario + ocd:altro_firmatario)
GRUPPI_QUERY          → nuova (batch 50 URI deputato)
STATO_ITER_QUERY      → nuova (storico completo, FILTER cursor-range)

# Funzioni
fetch_atti(leg)              → DataFrame  # copia da v1
fetch_firmatari(leg)         → DataFrame  # nuova — include primo e co
fetch_gruppi(uris, leg)      → DataFrame  # nuova
fetch_stati_iter(leg)        → DataFrame  # nuova — storico completo

# Main loop
per ogni legislatura:
  1. fetch_atti → df_atti
  2. fetch_firmatari → df_firmatari
  3. fetch_gruppi(uris da df_firmatari, leg) → df_gruppi
  4. fetch_stati_iter → df_stati
  5. merge
  6. scrivi atti_camera_v2.parquet e cofirmatari_camera.parquet
```

## CLI

```
uv run script_prova/fetch_metadati_camera_v2.py --legs 17
uv run script_prova/fetch_metadati_camera_v2.py --force
uv run script_prova/fetch_metadati_camera_v2.py --no-firmatari
uv run script_prova/fetch_metadati_camera_v2.py --dry-run
```

## Output

- `data/meta/atti_camera_v2.parquet` — schema esteso (vedi claude_T_camera_v2.md)
- `data/meta/cofirmatari_camera.parquet` — una riga per firmatario × atto
- `data/meta/coverage_camera_v2.parquet`
- `data/meta/fetch_log_camera_v2.json`

## Regole obbligatorie

- NON modificare `script/` né `fetch_metadati_camera.py`
- DuckDB COPY TO per tutti i Parquet
- SEMPRE SELECT DISTINCT e COUNT(DISTINCT) sull'endpoint Camera
- Keyset su STR(?atto), non su dc:identifier intero
- No VALUES blocks nelle query paginate → FILTER cursor-range
- Batch VALUES max 50 URI per query gruppi (fuori dalla paginazione principale)
- Commenti in inglese, citare scoperte diagnostiche con data ISO 8601
- Sleep 1s tra chiamate SPARQL, retry 3×
- Test su Leg17 prima del run completo

## Prima di scrivere il codice

Descrivi il piano in 5–7 punti e attendi conferma esplicita di Giacomo.
