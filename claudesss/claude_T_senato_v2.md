# claude_T_senato_v2.md — fetch_metadati_senato_v2.py
# Aggiunta: primo firmatario, cofirmatari, gruppo parlamentare, date iter

## Registro revisioni

| Data | Motivo |
|---|---|
| 2026-05-29 | Prima stesura — task definita |
| 2026-05-29 | Aggiunti §"Vincoli endpoint" e §"Risultati Leg17 confermati" dopo run di produzione |

---

## Obiettivo

Creare `script_prova/fetch_metadati_senato_v2.py` come estensione di `fetch_metadati_senato.py`.
Aggiunge per ogni DDL:
- Primo firmatario (senatore, nome, gruppo parlamentare in quella legislatura)
- Lista cofirmatari (senatore, nome, data firma, gruppo parlamentare)
- Gruppo parlamentare del primo firmatario alla data del DDL

## ONTOLOGIA DI RIFERIMENTO OBBLIGATORIA

Leggere prima di scrivere qualsiasi query:
`/Users/giacomosperti/Documents/Claude/Projects/Frag_Compl_data/iter-legis/docs/ontologia_senato.md`

---

## Catena firmatari — CONFERMATA EMPIRICAMENTE

```sparql
PREFIX osr: <http://dati.senato.it/osr/>

# Primo firmatario
?ddl osr:iniziativa ?iniz .
?iniz osr:primoFirmatario "1" ;     # xsd:string — NON booleano
      osr:senatore ?s_uri .
?s_uri foaf:firstName ?nome ;
       foaf:lastName  ?cognome .

# Cofirmatari (assenza di primoFirmatario="1")
?ddl osr:iniziativa ?iniz_co .
?iniz_co osr:senatore ?s_uri_co .
FILTER NOT EXISTS { ?iniz_co osr:primoFirmatario "1" }
OPTIONAL { ?iniz_co osr:dataAggiuntaFirma ?data_firma }
OPTIONAL { ?iniz_co osr:dataRitiroFirma   ?data_ritiro }
```

### Proprietà di osr:Iniziativa (tutte confermate nel triplestore)

| Proprietà | Tipo | Note |
|---|---|---|
| `osr:primoFirmatario` | string `"1"` | Flag primo firmatario |
| `osr:senatore` | URI `http://dati.senato.it/senatore/{id}` | ~30% delle Iniziativa ha questo link |
| `osr:presentatore` | string | Nome leggibile (= `descr_iniziativa` nel parquet) |
| `osr:tipoIniziativa` | string | "Parlamentare", "Governativa", "Regionale", "Popolare", "CNEL" |
| `osr:dataAggiuntaFirma` | string | Solo sui cofirmatari |
| `osr:dataRitiroFirma` | string | Data ritiro firma |

### Copertura osr:senatore

Solo ~30% delle `osr:Iniziativa` Parlamentare hanno il link `osr:senatore` — invariante su tutte le legislature (27.5–41.7%). Le Iniziativa senza `osr:senatore` hanno comunque `osr:presentatore` (nome testuale). Trattare come expected data gap.

---

## Catena gruppo parlamentare — CONFERMATA EMPIRICAMENTE (2026-05-29)

### Attenzione critica: osr:legislatura NON è su osr:Senatore

```sparql
# SBAGLIATO — restituisce sempre 0:
?s a osr:Senatore ; osr:legislatura 17 .

# CORRETTO — navigare via Iniziativa:
?ddl osr:iniziativa ?iniz .
?iniz osr:senatore ?s .
```

### Catena gruppo (testata, copertura 100% in Leg17)

```sparql
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT DISTINCT ?s ?gruppoURI ?titoloGruppo ?titoloBreve ?carica ?adGInizio ?adGFine WHERE {
  # Senatore via Iniziativa (NON via a osr:Senatore ; osr:legislatura N)
  ?ddl a osr:Ddl ;
       osr:legislatura ?leg ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?s .

  # Adesione al gruppo nella stessa legislatura
  ?s ocd:aderisce ?adG .
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura ?leg ;
       osr:gruppo ?gruppoURI ;
       osr:carica ?carica ;
       osr:inizio ?adGInizio .
  OPTIONAL { ?adG osr:fine ?adGFine . }

  # Nome del gruppo: denominazione valida nel periodo dell'adesione
  ?gruppoURI osr:denominazione ?dn .
  ?dn osr:titolo ?titoloGruppo ;
      osr:titoloBreve ?titoloBreve ;
      osr:inizio ?dnInizio .
  OPTIONAL { ?dn osr:fine ?dnFine . }
  FILTER(?dnInizio <= ?adGInizio &&
         (!bound(?dnFine) || ?dnFine >= ?adGInizio))
}
```

### Fatti critici sulla catena gruppo

- `ocd:aderisce` è **direttamente sul senatore** (URI `http://dati.senato.it/senatore/{id}`)
- Le adesioni sono **blank node** → NON navigabili come URI ma leggibili con SPARQL normale
- Un senatore può avere **più adesioni per legislatura** (cambio gruppo) — usare `DISTINCT` su `(s, gruppoURI)`
- Triplestore ha **blank node duplicati** → servono ulteriori `DISTINCT` su `(s, gruppoURI, adGInizio, adGFine)`
- `osr:denominazione` è un blank node con `osr:titolo` (nome completo) e `osr:titoloBreve` (sigla)
- **15 gruppi distinti** in Leg17
- **Copertura 100%** dei senatori raggiungibili via Iniziativa hanno adesioneGruppo in Leg17

### Classi coinvolte (namespace misto — normale)

| Proprietà/Classe | Namespace | Presente nel triplestore Senato |
|---|---|---|
| `ocd:aderisce` | Camera (`ocd:`) | ✅ SÌ — sul senatore URI |
| `ocd:adesioneGruppo` | Camera (`ocd:`) | ✅ 12.108 istanze |
| `osr:gruppo` | Senato (`osr:`) | ✅ — su adesioneGruppo |
| `ocd:gruppoParlamentare` | Camera (`ocd:`) | ✅ 188 istanze |
| `osr:denominazione` | Senato (`osr:`) | ✅ — su gruppoParlamentare, è blank node |
| `osr:titolo` | Senato (`osr:`) | ✅ — su denominazione bnode |
| `osr:titoloBreve` | Senato (`osr:`) | ✅ — su denominazione bnode |
| `osr:mandato` | Senato (`osr:`) | ✅ — URI named `http://dati.senato.it/mandato/S_{leg}_{id}_{n}` |

### Note: osr:mandato non serve per il gruppo

`osr:mandato` contiene legislatura, inizio, fine, tipo elezione — utile per l'anagrafica senatori ma NON è il percorso verso il gruppo. La catena è `ocd:aderisce → adesioneGruppo → osr:gruppo`, non `osr:mandato → ...`.

---

## Strategia di fetch — query separate

Per minimizzare il carico sull'endpoint e mantenere la struttura del codice esistente, usare query SEPARATE (non sub-query nella DDL_QUERY principale):

**Query A** (già esistente): metadati DDL principali — invariata

**Query B** (nuova): firmatari per legislatura
```sparql
SELECT DISTINCT ?ddl ?iniz ?s_uri ?presentatore ?tipo_iniziativa
                ?primo_firmatario ?data_firma ?data_ritiro WHERE {
  ?ddl a osr:Ddl ; osr:legislatura {leg} ; osr:iniziativa ?iniz .
  ?iniz osr:tipoIniziativa ?tipo_iniziativa .
  OPTIONAL { ?iniz osr:senatore        ?s_uri         }
  OPTIONAL { ?iniz osr:presentatore    ?presentatore  }
  OPTIONAL { ?iniz osr:primoFirmatario ?primo_firmatario }
  OPTIONAL { ?iniz osr:dataAggiuntaFirma ?data_firma  }
  OPTIONAL { ?iniz osr:dataRitiroFirma   ?data_ritiro }
  FILTER(?ddl_id_fase > {last_id})
}
ORDER BY ?ddl_id_fase
LIMIT {limit}
```

**Query C** (nuova): nomi senatori da foaf — FILTER IN, batch max 25 URI
```sparql
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX osr: <http://dati.senato.it/osr/>

SELECT DISTINCT ?s ?nome ?cognome ?label WHERE {
  ?s a osr:Senatore .
  OPTIONAL { ?s foaf:firstName ?nome    }
  OPTIONAL { ?s foaf:lastName  ?cognome }
  OPTIONAL { ?s rdfs:label     ?label   }
  FILTER(?s IN ({uris}))   -- comma-separated <uri> list, max 25
}
```

**Query D** (nuova): gruppo parlamentare via navigazione da DDL — SENZA URI batch
```sparql
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT DISTINCT ?s ?gruppoURI ?titoloGruppo ?titoloBreve ?carica ?adGInizio ?adGFine WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura {leg} ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?s .
  ?s ocd:aderisce ?adG .
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura {leg} ;
       osr:gruppo ?gruppoURI ;
       osr:carica ?carica ;
       osr:inizio ?adGInizio .
  OPTIONAL { ?adG osr:fine ?adGFine . }
  ?gruppoURI osr:denominazione ?dn .
  ?dn osr:titolo ?titoloGruppo ;
      osr:titoloBreve ?titoloBreve ;
      osr:inizio ?dnInizio .
  OPTIONAL { ?dn osr:fine ?dnFine . }
  FILTER(?dnInizio <= ?adGInizio &&
         (!bound(?dnFine) || ?dnFine >= ?adGInizio))
}
ORDER BY ?s
LIMIT {limit}
OFFSET {offset}
```

**Motivazione navigazione da DDL per Query D** (scoperta durante run 2026-05-29):
- `VALUES` non è supportato dall'endpoint (HTTP 400 — SPARQL 1.0 only)
- `FILTER IN` con 25 URI funziona per query semplici (Query C, ~1600 char URL)
- `FILTER IN` con la Query D completa supera il limite URL dell'endpoint anche a 25 URI
  (la Query D ha corpo ~500 char → totale URL > 2100 → HTTP 403)
- Navigazione da DDL restituisce tutti i senatori in una sola query paginata LIMIT/OFFSET
- Leg17: 803 righe in un'unica chiamata (333 senatori × ~2.4 adesioni medie)

---

## Schema output

### File principale: `data/meta/atti_senato_v2.parquet`

Tutte le colonne di `atti_senato.parquet` più:

| Colonna | Tipo | Descrizione |
|---|---|---|
| `uri_primo_firmatario` | str | URI senatore primo firmatario (null se non Parlamentare o no link) |
| `nome_primo_firmatario` | str | `foaf:firstName + foaf:lastName` del primo firmatario |
| `tipo_iniziativa` | str | "Parlamentare", "Governativa", "Regionale", "Popolare", "CNEL" |
| `gruppo_primo_firmatario_uri` | str | URI gruppo parlamentare (es. `http://dati.senato.it/gruppo/73`) |
| `gruppo_primo_firmatario_nome` | str | `osr:titolo` del gruppo (es. "Partito Democratico") |
| `gruppo_primo_firmatario_sigla` | str | `osr:titoloBreve` (es. "PD") |
| `n_cofirmatari` | int | Numero cofirmatari con link senatore |
| `n_cofirmatari_totale` | int | Numero totale firmatari (inclusi senza link) |

### File secondario: `data/meta/firmatari_senato.parquet`

Una riga per iniziativa (firmatario):

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id_fase` | str | ID fase DDL |
| `legislatura` | int | Numero legislatura |
| `uri_iniziativa` | str | URI dell'istanza osr:Iniziativa |
| `is_primo_firmatario` | bool | True se `osr:primoFirmatario = "1"` |
| `uri_senatore` | str | URI senatore (null se non disponibile) |
| `nome_senatore` | str | Nome leggibile (foaf o osr:presentatore) |
| `tipo_iniziativa` | str | Tipo iniziativa |
| `data_firma` | str | `osr:dataAggiuntaFirma` (solo cofirmatari) |
| `data_ritiro_firma` | str | `osr:dataRitiroFirma` |
| `gruppo_uri` | str | URI gruppo parlamentare |
| `gruppo_nome` | str | Nome gruppo |
| `gruppo_sigla` | str | Sigla gruppo |
| `carica_gruppo` | str | `osr:carica` in adesioneGruppo ("Membro", "Presidente", ecc.) |

---

## Vincoli endpoint Senato — confermati empiricamente (2026-05-29)

| Vincolo | Sintomo | Soluzione adottata |
|---|---|---|
| `VALUES` non supportato (SPARQL 1.0) | HTTP 400 Bad Request | Usare `FILTER(?s IN (...))` |
| Limite URL ~2100 char | HTTP 403 Forbidden (non 414) | Ridurre batch o evitare URI list |
| FILTER IN: soglia empirica 31 URI | URL 2063 char → OK; 2119 → 403 | `URI_BATCH_SIZE = 25` (margine sicuro) |
| GRUPPI_QUERY corpo lungo | 25 URI già superano il limite | Navigare da DDL (nessun URI in query) |

Regole operative:
- Non usare mai `VALUES` su questo endpoint
- Per query semplici (≤ 300 char corpo): `FILTER IN` con max 25 URI
- Per query complesse (> 300 char corpo): navigare dalla catena DDL/Iniziativa

---

## Risultati confermati — Leg17 (run 2026-05-29)

| Metrica | Valore |
|---|---|
| DDL totali | 8.004 (3.096 ramo S, 4.908 ramo C) |
| Righe firmatari (dopo dedup) | 83.064 |
| — di cui primo firmatario | 9.205 |
| — di cui cofirmatari | 73.859 |
| URI senatore presenti | 24.598 (29.7% delle righe) |
| URI uniche senatori | 333 |
| Nomi foaf risolti | 333/333 (100%) |
| Righe gruppi parlamentari | 803 (333 senatori × ~2.4 adesioni) |
| Copertura primo firmatario con URI (ramo S) | 2.554/3.096 = 82.5% |
| Copertura primo firmatario con URI (ramo C) | 51/4.908 = 1.0% (atteso) |
| Copertura primo firmatario con gruppo | pari a quella con URI (100% match) |

Distribuzione gruppi top-5 (firmatari totali):
`PD` 9.184 · `M5S` 3.804 · `Misto` 2.155 · `PdL` 1.358 · `Art.1-MDP` 1.347

---

## Convenzioni

- Script in `script_prova/fetch_metadati_senato_v2.py` (NON modificare `fetch_metadati_senato.py`)
- CLI: `--legs`, `--force`, `--dry-run`, `--no-emend`, `--no-firmatari`
- `URI_BATCH_SIZE = 25` per NOMI_QUERY (FILTER IN); GRUPPI_QUERY usa navigazione DDL senza batch
- DISTINCT su `(id_fase, uri_senatore, gruppo_uri, adGInizio)` per eliminare duplicati blank node
- Scrittura Parquet via DuckDB COPY TO
- Commenti in inglese, stile scientifico
