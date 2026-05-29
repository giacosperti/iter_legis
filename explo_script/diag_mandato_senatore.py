"""
diag_mandato_senatore.py
========================
Script diagnostico per la catena gruppo parlamentare dei senatori.

PROBLEMA CHE RISOLVE
--------------------
Il precedente script (diag_gruppo_iterdll_senato.py) falliva nelle sezioni G1-G4
perché usava il pattern:
    ?s a osr:Senatore ; osr:legislatura 17 .
che restituisce 0 risultati: osr:Senatore NON ha la proprietà osr:legislatura
(confermato dall'ontologia e dall'output del triplestore).

APPROCCIO CORRETTO
------------------
Per ottenere URI di senatori reali in Leg17, navigare dall'osr:Iniziativa:
    ?ddl a osr:Ddl ; osr:legislatura 17 ; osr:iniziativa ?iniz .
    ?iniz osr:senatore ?s .

Le tre sezioni:
  M1 — Ottieni URI senatore reale via osr:Iniziativa (Leg17)
  M2 — Dump di TUTTE le proprietà di quell'URI senatore
  M3 — Da osr:mandato, dump di TUTTE le proprietà dell'entità linkata
       + enumerazione dei tipi raggiunti per trovare il link al gruppo

ENDPOINT
--------
https://dati.senato.it/sparql
"""

import sys
from SPARQLWrapper import SPARQLWrapper, JSON

ENDPOINT = "https://dati.senato.it/sparql"


def run_query(sparql: SPARQLWrapper, query: str) -> list[dict]:
    """Esegue una query SPARQL e restituisce i risultati come lista di dict."""
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        results = sparql.query().convert()
        return results["results"]["bindings"]
    except Exception as e:
        print(f"  [ERRORE] {e}")
        return []


def val(binding: dict, key: str) -> str:
    """Estrae il valore di una variabile da un binding SPARQL."""
    b = binding.get(key)
    if b is None:
        return "(absent)"
    return b.get("value", "(no value)")


def print_sep(char="─", width=70):
    print(char * width)


def main():
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setTimeout(60)

    # ================================================================
    # M1 — URI senatore reale via osr:Iniziativa (Leg17)
    # ================================================================
    print_sep("=")
    print("M1 — URI senatore reale via osr:Iniziativa (Leg17)")
    print_sep("=")
    print()
    print("Pattern usato:")
    print("  ?ddl a osr:Ddl ; osr:legislatura 17 ; osr:iniziativa ?iniz .")
    print("  ?iniz osr:senatore ?s .")
    print("  (NO filtro su a osr:Senatore, NO filtro su osr:legislatura del senatore)")
    print()

    Q_M1 = """
PREFIX osr: <http://dati.senato.it/osr/>

SELECT DISTINCT ?s ?iniz ?ddl WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?s .
}
LIMIT 5
"""
    rows_m1 = run_query(sparql, Q_M1)
    print(f"  Risultati (LIMIT 5): {len(rows_m1)}")
    print()

    if not rows_m1:
        print("  [FALLITO] Nessun URI senatore trovato via osr:Iniziativa.")
        print("  Verificare se osr:iniziativa è su osr:Ddl o va navigato da osr:Atto.")
        print()

        # Tentativo alternativo: cerca osr:Iniziativa direttamente come tipo
        print("  → Tentativo alternativo: ?iniz a osr:Iniziativa ; osr:senatore ?s")
        print()
        Q_M1b = """
PREFIX osr: <http://dati.senato.it/osr/>

SELECT DISTINCT ?s ?iniz WHERE {
  ?iniz a osr:Iniziativa ;
        osr:senatore ?s .
}
LIMIT 5
"""
        rows_m1b = run_query(sparql, Q_M1b)
        print(f"  Risultati alternativo (LIMIT 5): {len(rows_m1b)}")
        for r in rows_m1b:
            print(f"    senatore URI : {val(r, 's')}")
            print(f"    iniziativa   : {val(r, 'iniz')}")
            print()
        # usa i risultati alternativi per M2/M3
        rows_m1 = rows_m1b

    else:
        for r in rows_m1:
            print(f"  senatore URI : {val(r, 's')}")
            print(f"  iniziativa   : {val(r, 'iniz')}")
            print(f"  ddl          : {val(r, 'ddl')}")
            print()

    # Estrai UN URI senatore per le sezioni successive
    s_uri = None
    for r in rows_m1:
        candidate = val(r, "s")
        if candidate.startswith("http"):
            s_uri = candidate
            break

    if s_uri is None:
        print("[STOP] Nessun URI senatore valido trovato. Interrompo lo script.")
        sys.exit(1)

    print(f"  >>> URI senatore scelto per M2/M3: {s_uri}")
    print()

    # ================================================================
    # M1b — Quanti senatori distinti raggiungibili via Iniziativa Leg17?
    # ================================================================
    print_sep()
    print("M1b — Conteggio senatori distinti via Iniziativa (tutte le legislature)")
    print_sep()
    print()

    # Conteggio globale
    Q_M1b_count = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {
  ?iniz a osr:Iniziativa ;
        osr:senatore ?s .
}
"""
    rows_count = run_query(sparql, Q_M1b_count)
    for r in rows_count:
        print(f"  Senatori DISTINTI (globale): {val(r, 'n')}")
    print()

    # Conteggio per leg17 via Ddl
    Q_M1b_leg17 = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?s .
}
"""
    rows_leg17 = run_query(sparql, Q_M1b_leg17)
    for r in rows_leg17:
        print(f"  Senatori DISTINTI (Leg17 via Ddl): {val(r, 'n')}")
    print()

    # ================================================================
    # M2 — Dump di TUTTE le proprietà dell'URI senatore scelto
    # ================================================================
    print_sep("=")
    print(f"M2 — Dump proprietà di: {s_uri}")
    print_sep("=")
    print()

    Q_M2 = f"""
SELECT ?pred ?obj WHERE {{
  <{s_uri}> ?pred ?obj .
}}
ORDER BY ?pred
"""
    rows_m2 = run_query(sparql, Q_M2)
    print(f"  Proprietà trovate: {len(rows_m2)}")
    print()

    if not rows_m2:
        print("  [ATTENZIONE] Nessuna proprietà diretta. L'URI potrebbe essere vuoto nel triplestore.")
        print("  Provo come soggetto di triple inverse (il soggetto punta a quest'URI)...")
        print()
        Q_M2_inv = f"""
SELECT ?subj ?pred WHERE {{
  ?subj ?pred <{s_uri}> .
}}
LIMIT 20
"""
        rows_m2_inv = run_query(sparql, Q_M2_inv)
        print(f"  Triple inverse trovate: {len(rows_m2_inv)}")
        for r in rows_m2_inv:
            print(f"    {val(r, 'subj')} --[{val(r, 'pred')}]--> {s_uri}")
        print()
    else:
        for r in rows_m2:
            pred = val(r, "pred")
            obj  = val(r, "obj")
            # Abbrevia i prefissi comuni
            pred_short = pred.replace("http://dati.senato.it/osr/", "osr:") \
                             .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:") \
                             .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:") \
                             .replace("http://xmlns.com/foaf/0.1/", "foaf:") \
                             .replace("http://dati.camera.it/ocd/", "ocd:") \
                             .replace("http://www.w3.org/2001/XMLSchema#", "xsd:")
            obj_short  = obj.replace("http://dati.senato.it/osr/", "osr:") \
                            .replace("http://dati.senato.it/senatore/", "sen:") \
                            .replace("http://dati.camera.it/ocd/", "ocd:")
            print(f"  {pred_short:<45} {obj_short}")
        print()

    # Cerca se ci sono mandati nella lista
    mandato_uris = []
    for r in rows_m2:
        pred = val(r, "pred")
        obj  = val(r, "obj")
        if "mandato" in pred.lower() or "mandato" in obj.lower():
            mandato_uris.append(obj)

    print(f"  URI di tipo 'mandato' trovati nelle proprietà: {len(mandato_uris)}")
    for m in mandato_uris:
        print(f"    {m}")
    print()

    # ================================================================
    # M2b — Se nessun mandato trovato, cerca il tipo dell'URI senatore
    # ================================================================
    print_sep()
    print("M2b — Tipo RDF dell'URI senatore (rdf:type)")
    print_sep()
    print()

    Q_M2b = f"""
SELECT ?type WHERE {{
  <{s_uri}> a ?type .
}}
"""
    rows_m2b = run_query(sparql, Q_M2b)
    if rows_m2b:
        for r in rows_m2b:
            print(f"  rdf:type: {val(r, 'type')}")
    else:
        print("  (nessun rdf:type diretto)")
    print()

    # ================================================================
    # M3 — Dump proprietà dei mandati raggiungibili dall'URI senatore
    # ================================================================
    print_sep("=")
    print("M3 — Dump proprietà dei mandati via osr:mandato")
    print_sep("=")
    print()

    # Query generica: qualunque pred punta a un'entità con osr:mandato
    Q_M3_direct = f"""
PREFIX osr: <http://dati.senato.it/osr/>

SELECT ?m ?pred ?obj WHERE {{
  <{s_uri}> osr:mandato ?m .
  ?m ?pred ?obj .
}}
ORDER BY ?m ?pred
LIMIT 100
"""
    rows_m3 = run_query(sparql, Q_M3_direct)
    print(f"  Triple dal pattern <{s_uri}> osr:mandato ?m: {len(rows_m3)}")
    print()

    if not rows_m3:
        print("  Nessun risultato con osr:mandato diretto.")
        print("  → Provo con ocd:rif_mandatoSenato ...")
        print()
        Q_M3_rif = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT ?m ?pred ?obj WHERE {{
  <{s_uri}> ocd:rif_mandatoSenato ?m .
  ?m ?pred ?obj .
}}
ORDER BY ?m ?pred
LIMIT 100
"""
        rows_m3_rif = run_query(sparql, Q_M3_rif)
        print(f"  Triple da ocd:rif_mandatoSenato: {len(rows_m3_rif)}")
        rows_m3 = rows_m3_rif
        print()

    # Stampa risultati M3
    mandato_seen = set()
    for r in rows_m3:
        m    = val(r, "m")
        pred = val(r, "pred")
        obj  = val(r, "obj")
        if m not in mandato_seen:
            mandato_seen.add(m)
            print(f"  --- Mandato: {m} ---")
        pred_short = pred.replace("http://dati.senato.it/osr/", "osr:") \
                         .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:") \
                         .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:") \
                         .replace("http://dati.camera.it/ocd/", "ocd:") \
                         .replace("http://xmlns.com/foaf/0.1/", "foaf:")
        print(f"    {pred_short:<45} {obj}")
    print()

    # ================================================================
    # M3b — Da mandato, cerca il gruppo parlamentare
    # ================================================================
    print_sep("=")
    print("M3b — Gruppo parlamentare dal mandato")
    print_sep("=")
    print()

    # Tentativo 1: ocd:adesioneGruppo → osr:gruppo
    Q_M3b_1 = f"""
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT ?m ?adGruppo ?gruppo ?label WHERE {{
  <{s_uri}> osr:mandato ?m .
  ?adGruppo ocd:rif_mandatoSenato ?m .
  OPTIONAL {{ ?adGruppo osr:gruppo ?gruppo . }}
  OPTIONAL {{ ?gruppo rdfs:label ?label . }}
}}
LIMIT 10
"""
    print("  Tentativo A: mandato → ocd:adesioneGruppo (via rif_mandatoSenato) → osr:gruppo")
    rows_m3b_1 = run_query(sparql, Q_M3b_1)
    print(f"  Risultati: {len(rows_m3b_1)}")
    for r in rows_m3b_1:
        print(f"    mandato    : {val(r, 'm')}")
        print(f"    adGruppo   : {val(r, 'adGruppo')}")
        print(f"    gruppo     : {val(r, 'gruppo')}")
        print(f"    label      : {val(r, 'label')}")
        print()
    print()

    # Tentativo 2: cerca soggetti che puntano al mandato
    Q_M3b_2 = f"""
PREFIX osr: <http://dati.senato.it/osr/>

SELECT ?mandURI ?subj ?pred WHERE {{
  <{s_uri}> osr:mandato ?mandURI .
  ?subj ?pred ?mandURI .
}}
LIMIT 20
"""
    print("  Tentativo B: chi punta al mandato? (?subj ?pred mandatoURI)")
    rows_m3b_2 = run_query(sparql, Q_M3b_2)
    print(f"  Risultati: {len(rows_m3b_2)}")
    for r in rows_m3b_2:
        print(f"    {val(r, 'subj')} --[{val(r, 'pred')}]--> {val(r, 'mandURI')}")
    print()

    # Tentativo 3: cerca chi punta al senatore con proprietà contenenti "gruppo"
    Q_M3b_3 = f"""
SELECT ?subj ?pred ?obj WHERE {{
  {{ <{s_uri}> ?pred ?obj . FILTER(contains(lcase(str(?pred)), "gruppo")) }}
  UNION
  {{ ?subj ?pred <{s_uri}> . FILTER(contains(lcase(str(?pred)), "gruppo")) }}
}}
LIMIT 20
"""
    print("  Tentativo C: qualunque proprietà contenente 'gruppo' legata al senatore")
    rows_m3b_3 = run_query(sparql, Q_M3b_3)
    print(f"  Risultati: {len(rows_m3b_3)}")
    for r in rows_m3b_3:
        print(f"    sogg: {val(r, 'subj')}  pred: {val(r, 'pred')}  ogg: {val(r, 'obj')}")
    print()

    # ================================================================
    # M4 — Esplorazione globale: cosa c'è nella classe ocd:adesioneGruppo?
    # ================================================================
    print_sep("=")
    print("M4 — Esplorazione classe ocd:adesioneGruppo nel triplestore Senato")
    print_sep("=")
    print()

    Q_M4_count = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(?x) AS ?n) WHERE {
  ?x a ocd:adesioneGruppo .
}
"""
    rows_m4_count = run_query(sparql, Q_M4_count)
    for r in rows_m4_count:
        print(f"  Istanze di ocd:adesioneGruppo: {val(r, 'n')}")
    print()

    Q_M4_sample = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?x ?pred ?obj WHERE {
  ?x a ocd:adesioneGruppo .
  ?x ?pred ?obj .
}
LIMIT 30
"""
    rows_m4_sample = run_query(sparql, Q_M4_sample)
    print(f"  Sample proprietà (LIMIT 30): {len(rows_m4_sample)}")
    print()

    seen_ag = set()
    for r in rows_m4_sample:
        x    = val(r, "x")
        pred = val(r, "pred")
        obj  = val(r, "obj")
        if x not in seen_ag:
            seen_ag.add(x)
            print(f"  --- adesioneGruppo: {x} ---")
        pred_short = pred.replace("http://dati.senato.it/osr/", "osr:") \
                         .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:") \
                         .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:") \
                         .replace("http://dati.camera.it/ocd/", "ocd:") \
                         .replace("http://xmlns.com/foaf/0.1/", "foaf:")
        print(f"    {pred_short:<45} {obj}")
    print()

    # ================================================================
    # M5 — Esplorazione classe ocd:gruppoParlamentare nel triplestore Senato
    # ================================================================
    print_sep("=")
    print("M5 — Esplorazione classe ocd:gruppoParlamentare nel triplestore Senato")
    print_sep("=")
    print()

    Q_M5_count = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(?x) AS ?n) WHERE {
  ?x a ocd:gruppoParlamentare .
}
"""
    rows_m5_count = run_query(sparql, Q_M5_count)
    for r in rows_m5_count:
        print(f"  Istanze di ocd:gruppoParlamentare: {val(r, 'n')}")
    print()

    Q_M5_sample = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?x ?pred ?obj WHERE {
  ?x a ocd:gruppoParlamentare .
  ?x ?pred ?obj .
}
LIMIT 30
"""
    rows_m5_sample = run_query(sparql, Q_M5_sample)
    print(f"  Sample proprietà (LIMIT 30): {len(rows_m5_sample)}")
    print()

    seen_gp = set()
    for r in rows_m5_sample:
        x    = val(r, "x")
        pred = val(r, "pred")
        obj  = val(r, "obj")
        if x not in seen_gp:
            seen_gp.add(x)
            print(f"  --- gruppoParlamentare: {x} ---")
        pred_short = pred.replace("http://dati.senato.it/osr/", "osr:") \
                         .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:") \
                         .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:") \
                         .replace("http://dati.camera.it/ocd/", "ocd:") \
                         .replace("http://xmlns.com/foaf/0.1/", "foaf:")
        print(f"    {pred_short:<45} {obj}")
    print()

    # ================================================================
    # M6 — Riepilogo
    # ================================================================
    print_sep("=")
    print("M6 — RIEPILOGO")
    print_sep("=")
    print()
    print("Interpretare i risultati delle sezioni M1-M5 per rispondere:")
    print()
    print("  1. URI senatore reale trovato?       →", "SÌ" if s_uri else "NO", f"({s_uri})")
    print("  2. Proprietà dell'URI senatore?       →", f"{len(rows_m2)} triple")
    print("  3. osr:mandato presente?              →", "SÌ" if mandato_uris else "NO (0 trovati con keyword 'mandato')")
    print("  4. Proprietà del mandato?             →", f"{len(rows_m3)} triple")
    print("  5. ocd:adesioneGruppo presente?       →", f"{len(rows_m4_sample)} triple campione")
    print("  6. ocd:gruppoParlamentare presente?   →", f"{len(rows_m5_sample)} triple campione")
    print()
    print("Se ocd:adesioneGruppo o ocd:gruppoParlamentare hanno istanze, la catena esiste")
    print("nel triplestore Senato. Analizzare le loro proprietà per trovare il link")
    print("al senatore e alla legislatura.")
    print()
    print_sep("=")
    print("Fine script diag_mandato_senatore.py")
    print_sep("=")


if __name__ == "__main__":
    main()
