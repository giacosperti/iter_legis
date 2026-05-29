"""
diag_ocdac_camera.py
====================
Verifica empirica di ocd:ac sul triplestore Camera.

ocd:ac è definita nell'ontologia Camera OWL con:
  - IRI:    http://dati.camera.it/ocd/ac
  - label:  "URL dell'atto camera"
  - domain: ocd:atto (tra gli altri)

La diagnosi originale riportava 0 risultati — questo script verifica
se la proprietà è effettivamente popolata o meno nel triplestore.
"""

from SPARQLWrapper import SPARQLWrapper, JSON

ENDPOINT = "https://dati.camera.it/sparql"


def run(sparql, query):
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        return sparql.query().convert()["results"]["bindings"]
    except Exception as e:
        print(f"  [ERRORE] {e}")
        return []


def val(r, k):
    return r[k]["value"] if k in r else "(assente)"


def sep(c="─", w=70): print(c * w)


def main():
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setTimeout(30)

    # ── Q1: ocd:ac su ocd:atto ───────────────────────────────────────────
    sep("=")
    print("Q1 — ocd:ac su ocd:atto (LIMIT 10)")
    sep("=")

    Q1 = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?atto ?url WHERE {
  ?atto a ocd:atto ;
        ocd:ac ?url .
}
LIMIT 10
"""
    rows = run(sparql, Q1)
    print(f"  Risultati: {len(rows)}")
    for r in rows:
        print(f"  atto : {val(r, 'atto')}")
        print(f"  ac   : {val(r, 'url')}")
        print()

    # ── Q2: COUNT totale ──────────────────────────────────────────────────
    sep()
    print("Q2 — COUNT(DISTINCT atto) con ocd:ac popolata")
    sep()

    Q2 = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(DISTINCT ?atto) AS ?n) WHERE {
  ?atto a ocd:atto ;
        ocd:ac ?url .
}
"""
    rows2 = run(sparql, Q2)
    for r in rows2:
        print(f"  n = {val(r, 'n')}")
    print()

    # ── Q3: ocd:ac su qualunque subject (trova CHI la usa davvero) ───────
    sep()
    print("Q3 — ocd:ac su qualunque subject (LIMIT 10)")
    sep()

    Q3 = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?s ?type ?url WHERE {
  ?s ocd:ac ?url .
  OPTIONAL { ?s a ?type . }
}
LIMIT 10
"""
    rows3 = run(sparql, Q3)
    print(f"  Risultati: {len(rows3)}")
    for r in rows3:
        print(f"  s    : {val(r, 's')}")
        print(f"  type : {val(r, 'type')}")
        print(f"  ac   : {val(r, 'url')}")
        print()

    # ── Q4: legatura Leg17 — ocd:ac per legislatura ──────────────────────
    sep()
    print("Q4 — COUNT ocd:ac per legislatura (Leg16–19)")
    sep()

    for leg in [16, 17, 18, 19]:
        Q4 = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(DISTINCT ?atto) AS ?n) WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_{leg}> ;
        ocd:ac ?url .
}}
"""
        rows4 = run(sparql, Q4)
        n = rows4[0]["n"]["value"] if rows4 else "?"
        print(f"  Leg{leg}: {n} atti con ocd:ac")
    print()

    sep("=")
    print("Fine diag_ocdac_camera.py")
    sep("=")


if __name__ == "__main__":
    main()
