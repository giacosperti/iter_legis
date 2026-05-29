# Prompt — fetch_metadati_senato_v2.py

## Contesto operativo

Leggi prima, nell'ordine:
1. `iter-legis/CLAUDE.md` — regole universali del progetto
2. `iter-legis/claudesss/claude_T_senato_v2.md` — specifiche complete di questo task
3. `/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/ontologia_senato.md` — ontologia Senato (obbligatorio prima di scrivere query SPARQL)
4. `iter-legis/script_prova/fetch_metadati_senato.py` — script base di cui questo è l'estensione

## Task

Crea `script_prova/fetch_metadati_senato_v2.py`. NON modificare `fetch_metadati_senato.py`.

Aggiunge al fetch DDL Senato (Leg13–19):
- Primo firmatario per DDL (senatore URI, nome, tipo iniziativa)
- Cofirmatari per DDL (senatore URI, nome, data firma, data ritiro)
- Gruppo parlamentare per ogni firmatario nella legislatura del DDL

---

## Fatti tecnici critici — leggere con attenzione

### osr:Senatore NON ha osr:legislatura

Questo pattern restituisce SEMPRE 0 risultati e NON deve mai comparire nel codice:
```sparql
# SBAGLIATO — non usare mai:
?s a osr:Senatore ; osr:legislatura 17 .
```

Per ottenere senatori di una legislatura: navigare da `osr:Iniziativa`:
```sparql
?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:iniziativa ?iniz .
?iniz osr:senatore ?s .
```

### Struttura osr:Iniziativa (confermata empiricamente)

```sparql
?ddl osr:iniziativa ?iniz .
?iniz osr:tipoIniziativa    ?tipo          .   # "Parlamentare", "Governativa", ...
?iniz osr:primoFirmatario   "1"            .   # xsd:string "1", NON booleano
?iniz osr:senatore          ?s_uri         .   # presente solo nel ~30% dei casi
?iniz osr:presentatore      ?nome_text     .   # sempre presente — nome leggibile
OPTIONAL { ?iniz osr:dataAggiuntaFirma ?data_firma   }  # solo cofirmatari
OPTIONAL { ?iniz osr:dataRitiroFirma   ?data_ritiro  }
```

### Catena gruppo parlamentare (confermata, copertura 100% in Leg17)

```sparql
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT DISTINCT ?s ?gruppoURI ?titoloGruppo ?titoloBreve ?carica ?adGInizio ?adGFine WHERE {
  ?s ocd:aderisce ?adG .
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura {leg} ;     # legislatura sull'adesioneGruppo, NON sul senatore
       osr:gruppo      ?gruppoURI ;
       osr:carica      ?carica ;
       osr:inizio      ?adGInizio .
  OPTIONAL { ?adG osr:fine ?adGFine . }

  ?gruppoURI osr:denominazione ?dn .
  ?dn osr:titolo      ?titoloGruppo ;
      osr:titoloBreve ?titoloBreve ;
      osr:inizio      ?dnInizio .
  OPTIONAL { ?dn osr:fine ?dnFine . }
  # Filtra la denominazione valida nel periodo dell'adesione
  FILTER(?dnInizio <= ?adGInizio &&
         (!bound(?dnFine) || ?dnFine >= ?adGInizio))
}
```

Dove `VALUES ?s { {uris} }` con batch massimo 50 URI.

### Duplicati blank node nel triplestore

I blank node `adesioneGruppo` sono duplicati nel triplestore. Usare sempre:
```sparql
SELECT DISTINCT ?s ?gruppoURI ?adGInizio ?adGFine ...
```
In Python, dopo il fetch, deduplicare ulteriormente su `(uri_senatore, gruppo_uri, adGInizio)`.

### Nomi senatori

```sparql
SELECT DISTINCT ?s ?nome ?cognome WHERE {
  VALUES ?s { {uris} }
  OPTIONAL { ?s foaf:firstName ?nome    }
  OPTIONAL { ?s foaf:lastName  ?cognome }
}
```
Se `foaf:firstName` e `foaf:lastName` assenti, usare `osr:presentatore` dall'Iniziativa come fallback.

---

## Struttura del codice da seguire

Stessa architettura di `fetch_metadati_senato.py`:

```
SPARQL_ENDPOINT, HEADERS, CHUNK, MAX_RETRY, SLEEP_BETWEEN
sparql(query, timeout) → list[dict]
val(binding, key) → str | None
write_parquet(df, path) → None   # DuckDB COPY TO — NON pandas.to_parquet()

# Query principali
DDL_QUERY        → invariata da fetch_metadati_senato.py
FIRMATARI_QUERY  → nuova (per osr:Iniziativa — keyset su id_fase)
NOMI_QUERY       → nuova (batch 50 URI senatore)
GRUPPI_QUERY     → nuova (batch 50 URI senatore × legislatura)

# Funzioni fetch
fetch_ddl(leg, dry_run)              → DataFrame  # copia da v1
fetch_firmatari(leg, dry_run)        → DataFrame  # nuova
fetch_nomi_senatori(uris)            → dict[uri→(nome,cognome)]  # nuova
fetch_gruppi(uris, leg, dry_run)     → DataFrame  # nuova
fetch_emend_counts(leg, dry_run)     → DataFrame  # copia da v1

# Main loop
per ogni legislatura:
  1. fetch_ddl → df_ddl
  2. fetch_firmatari → df_firmatari
  3. fetch_nomi_senatori(uris da df_firmatari) → dict nomi
  4. fetch_gruppi(uris da df_firmatari, leg) → df_gruppi
  5. merge tutto
  6. scrivi atti_senato_v2.parquet e firmatari_senato.parquet
```

## CLI

```
uv run script_prova/fetch_metadati_senato_v2.py --legs 17
uv run script_prova/fetch_metadati_senato_v2.py --force
uv run script_prova/fetch_metadati_senato_v2.py --no-emend --no-firmatari   # solo DDL base
uv run script_prova/fetch_metadati_senato_v2.py --dry-run
```

## Output

- `data/meta/atti_senato_v2.parquet` — schema esteso (vedi claude_T_senato_v2.md)
- `data/meta/firmatari_senato.parquet` — una riga per firmatario × DDL
- `data/meta/coverage_senato_v2.parquet`
- `data/meta/fetch_log_senato_v2.json`

## Regole obbligatorie

- NON modificare `script/` né `fetch_metadati_senato.py`
- DuckDB COPY TO per tutti i Parquet
- Commenti in inglese, citare le scoperte diagnostiche con data ISO 8601
- Sleep 1s tra chiamate SPARQL
- Retry 3× con 5s di attesa
- Idempotente: skip legislatura se output già esiste (override con `--force`)
- Batch VALUES max 50 URI (HTTP 400 su batch grandi)
- DISTINCT su `(id_fase, uri_senatore, gruppo_uri, adGInizio)` per deduplicare blank node
- Test su Leg17 prima del run completo

## Prima di scrivere il codice

Descrivi il piano in 5–7 punti e attendi conferma esplicita di Giacomo.
