# Product Requirements Document (PRD)

## 1. Obiettivo del Progetto
Costruire un dataset strutturato dei processi legislativi del Senato Italiano (standard Akoma Ntoso) per analizzare la relazione tra frammentazione politica e complessità legislativa.

## 2. Principi Architetturali Mandatori
### 2.1 Idempotenza
Ogni fase di elaborazione (script) deve essere **idempotente**. 
*   L'esecuzione multipla dello stesso script sullo stesso input deve produrre lo stesso output.
*   Il sistema deve verificare l'esistenza di dati già processati prima di procedere (sovrascrittura sicura o skip).
*   Non devono essere creati record duplicati nel dataset finale in caso di ri-esecuzione.

### 2.2 Modularità (Step-by-Step)
Il progetto è diviso in fasi discrete. Ogni fase deve produrre un output verificabile (JSON/CSV) che serva da input per la fase successiva.
*   **Fase 1: DDL Parsing.** Estrazione struttura e metadati base dai testi originali.
*   **Fase 2: Amendment Parsing.** Estrazione e mappatura degli emendamenti sugli articoli del DDL.
*   **Fase 3: Political Mapping.** Associazione dei proponenti a partiti/gruppi e status (maggioranza/opposizione).
*   **Fase 4: Metrics Computation.** Calcolo di complessità, distanza testuale e similarità.

### 2.3 Tracciabilità
Ogni dato nel dataset finale deve essere riconducibile alla fonte originale (URI Akoma Ntoso, ID Atto, ID Emendamento).

### 2.4 Compatibilità con Flattening (Spreadsheet-Ready)
La struttura dei dati deve essere progettata per essere facilmente "appiattita" (es. tramite strumenti come `flatten-tool`).
*   Ogni oggetto nidificato (es. proponenti in un emendamento) deve avere un riferimento chiaro all'ID del genitore.
*   Il formato finale deve permettere l'esportazione in CSV/XLSX senza perdita di relazioni (schema relazionale).

## 3. Requisiti Funzionali per Fase

### Fase 1: Parsing DDL (Completata)
*   **Input:** File XML Akoma Ntoso (`ddlpres`).
*   **Output:** JSON strutturato con metadati (date, firmatari) e gerarchia (articoli, commi).
*   **Stato:** Funzionante tramite `script/parser_ddl.py`.

### Fase 2: Parsing Emendamenti (In Corso)
*   **Input:** File XML Akoma Ntoso (`emend` o `emendc`).
*   **Requisiti:** 
    *   Identificare articolo/comma target.
    *   Estrarre proponenti.
    *   Distinguere tipo di operazione (soppressione, modifica, aggiunta).
*   **Idempotenza:** Se un fascicolo di emendamenti viene ri-processato, gli emendamenti già estratti devono essere aggiornati o mantenuti senza duplicati.

### Fase 3: Mapping Politico
*   **Input:** Risultati Fasi 1-2 + Database/API cariche politiche.
*   **Requisiti:** Determinare lo schieramento del proponente alla data specifica dell'emendamento.

### Fase 4: Analisi e Metriche
*   **Input:** Dataset consolidato.
*   **Metriche:** Indici di leggibilità, conteggio riferimenti normativi, clustering di similarità testuale tra emendamenti.

## 4. Gestione Dati Locali
*   I dati grezzi devono essere salvati in una struttura speculare al repository Senato: `data/Leg[N]/Atto[ID]/[Tipo]/`.
*   Gli output processati devono seguire la stessa gerarchia per facilitare il debug.

## 5. Validazione
Ogni fase deve includere un controllo di integrità (es. numero di articoli estratti vs numero atteso, assenza di campi nulli critici).
