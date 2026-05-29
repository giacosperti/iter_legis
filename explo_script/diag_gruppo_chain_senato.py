"""
diag_gruppo_chain_senato.py
===========================
Script diagnostico finale per la catena gruppo parlamentare senatori.

OBIETTIVO
---------
Chiudere i due punti aperti dopo diag_mandato_senatore.py:

  G-CHAIN  Verifica la catena completa senatore → adesioneGruppo → gruppo
           su un URI senatore reale in Leg17 (filtro su osr:legislatura
           dentro il blank node, non sul senatore direttamente)

  G-DENOM  Esplora il blank node osr:denominazione su ocd:gruppoParlamentare
           per trovare il nome testuale del gruppo

  G-STAT   Statistica: quanti senatori Leg17 hanno almeno una adesioneGruppo
           in Leg17? Distribuzione per osr:carica.

  G-NAME   Costruisce la lista gruppo-nome per Leg17 (URI → stringa).
"""

from SPARQLWrapper import SPARQLWrapper, JSON

ENDPOINT = "https://dati.senato.it/sparql"
SEN_URI  = "http://dati.senato.it/senatore/29033"   # Piero Aiello, Leg17
GRUPPO_URI = "http://dati.senato.it/gruppo/49"


def run(sparql, query):
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        return sparql.query().convert()["results"]["bindings"]
    except Exception as e:
        print(f"  [ERRORE] {e}")
        return []


def sep(c="─", w=70): print(c * w)


def main():
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setTimeout(60)

    # ================================================================
    # G-CHAIN — Catena completa: senatore → adesioneGruppo → gruppo
    # ================================================================
    sep("=")
    print("G-CHAIN — Catena completa senatore → adesioneGruppo → gruppo (Leg17)")
    sep("=")
    print()

    Q_CHAIN = f"""
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT ?adG ?leg ?gruppo ?carica ?inizio ?fine WHERE {{
  <{SEN_URI}> ocd:aderisce ?adG .
  ?adG osr:legislatura ?leg ;
       osr:gruppo      ?gruppo ;
       osr:carica      ?carica .
  OPTIONAL {{ ?adG osr:inizio ?inizio . }}
  OPTIONAL {{ ?adG osr:fine   ?fine   . }}
  FILTER(?leg = 17)
}}
ORDER BY ?inizio
"""
    rows = run(sparql, Q_CHAIN)
    print(f"  Senatore: {SEN_URI}")
    print(f"  Adesioni Leg17: {len(rows)}")
    print()
    for r in rows:
        def v(k): return r[k]["value"] if k in r else "(assente)"
        print(f"  adesioneGruppo : {v('adG')}")
        print(f"  legislatura    : {v('leg')}")
        print(f"  gruppo URI     : {v('gruppo')}")
        print(f"  carica         : {v('carica')}")
        print(f"  inizio         : {v('inizio')}")
        print(f"  fine           : {v('fine')}")
        print()

    # ================================================================
    # G-DENOM — Cosa c'è nel blank node osr:denominazione?
    # ================================================================
    sep("=")
    print(f"G-DENOM — Contenuto di osr:denominazione su {GRUPPO_URI}")
    sep("=")
    print()

    Q_DENOM = f"""
PREFIX osr: <http://dati.senato.it/osr/>

SELECT ?denom ?pred ?val WHERE {{
  <{GRUPPO_URI}> osr:denominazione ?denom .
  ?denom ?pred ?val .
}}
ORDER BY ?denom ?pred
LIMIT 40
"""
    rows_d = run(sparql, Q_DENOM)
    print(f"  Triple trovate (LIMIT 40): {len(rows_d)}")
    print()

    denom_seen = set()
    for r in rows_d:
        def v(k): return r[k]["value"] if k in r else "(assente)"
        denom = v("denom")
        pred  = v("pred").replace("http://dati.senato.it/osr/", "osr:") \
                         .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:") \
                         .replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:")
        val   = v("val")
        if denom not in denom_seen:
            denom_seen.add(denom)
            print(f"  --- denominazione bnode: {denom} ---")
        print(f"    {pred:<40} {val}")
    print()

    # ================================================================
    # G-NAME — Lista gruppo URI → nome per Leg17
    # ================================================================
    sep("=")
    print("G-NAME — URI gruppo → nome testuale (Leg17)")
    sep("=")
    print()

    # Tentativo 1: denominazione → valore testuale diretto
    Q_NAME1 = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT DISTINCT ?gruppo ?nome WHERE {
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura 17 ;
       osr:gruppo ?gruppo .
  ?gruppo osr:denominazione ?denomBnode .
  ?denomBnode osr:nome ?nome .
}
ORDER BY ?gruppo
"""
    print("  Tentativo A: gruppo → denominazione bnode → osr:nome")
    rows_n1 = run(sparql, Q_NAME1)
    print(f"  Risultati: {len(rows_n1)}")
    for r in rows_n1:
        def v(k): return r[k]["value"] if k in r else "(assente)"
        print(f"    {v('gruppo'):<50}  {v('nome')}")
    print()

    # Tentativo 2: rdfs:label diretto sul gruppo
    Q_NAME2 = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?gruppo ?label WHERE {
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura 17 ;
       osr:gruppo ?gruppo .
  OPTIONAL { ?gruppo rdfs:label ?label . }
}
ORDER BY ?gruppo
"""
    print("  Tentativo B: gruppo → rdfs:label diretto")
    rows_n2 = run(sparql, Q_NAME2)
    print(f"  Risultati: {len(rows_n2)}")
    for r in rows_n2:
        def v(k): return r[k]["value"] if k in r else "(assente)"
        print(f"    {v('gruppo'):<50}  {v('label')}")
    print()

    # Tentativo 3: qualunque stringa nelle denominazione bnode
    Q_NAME3 = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT DISTINCT ?gruppo ?pred ?val WHERE {
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura 17 ;
       osr:gruppo ?gruppo .
  ?gruppo osr:denominazione ?dn .
  ?dn ?pred ?val .
  FILTER(isLiteral(?val))
}
ORDER BY ?gruppo ?pred
LIMIT 60
"""
    print("  Tentativo C: tutti i letterali nei bnode denominazione (Leg17)")
    rows_n3 = run(sparql, Q_NAME3)
    print(f"  Risultati (LIMIT 60): {len(rows_n3)}")
    grp_seen = set()
    for r in rows_n3:
        def v(k): return r[k]["value"] if k in r else "(assente)"
        grp = v("gruppo")
        pred = v("pred").replace("http://dati.senato.it/osr/", "osr:")
        val  = v("val")
        if grp not in grp_seen:
            grp_seen.add(grp)
            print(f"\n  --- {grp} ---")
        print(f"    {pred:<35} {val}")
    print()

    # ================================================================
    # G-STAT — Quanti senatori Leg17 hanno adesioneGruppo in Leg17?
    # ================================================================
    sep("=")
    print("G-STAT — Copertura: senatori Leg17 con adesioneGruppo in Leg17")
    sep("=")
    print()

    # Totale senatori distinti in Leg17 (via Iniziativa)
    Q_TOT = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?s .
}
"""
    rows_tot = run(sparql, Q_TOT)
    n_tot = int(rows_tot[0]["n"]["value"]) if rows_tot else "?"
    print(f"  Senatori Leg17 (via Iniziativa): {n_tot}")

    # Senatori con almeno una adesioneGruppo in Leg17
    Q_CON = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 17 ;
       osr:iniziativa ?iniz .
  ?iniz osr:senatore ?s .
  ?s ocd:aderisce ?adG .
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura 17 .
}
"""
    rows_con = run(sparql, Q_CON)
    n_con = int(rows_con[0]["n"]["value"]) if rows_con else "?"
    print(f"  Con adesioneGruppo Leg17       : {n_con}")
    if isinstance(n_tot, int) and isinstance(n_con, int) and n_tot > 0:
        print(f"  Copertura                      : {n_con/n_tot*100:.1f}%")
    print()

    # Distribuzione per carica
    Q_CARICA = """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?carica (COUNT(DISTINCT ?s) AS ?n) WHERE {
  ?s ocd:aderisce ?adG .
  ?adG a ocd:adesioneGruppo ;
       osr:legislatura 17 ;
       osr:carica ?carica .
}
GROUP BY ?carica
ORDER BY DESC(?n)
"""
    rows_car = run(sparql, Q_CARICA)
    print("  Distribuzione per osr:carica (Leg17):")
    for r in rows_car:
        def v(k): return r[k]["value"] if k in r else "(assente)"
        print(f"    {v('carica'):<40} n={v('n')}")
    print()

    sep("=")
    print("Fine script diag_gruppo_chain_senato.py")
    sep("=")


if __name__ == "__main__":
    main()
