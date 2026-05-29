#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
diag_camera_allegati_url.py — Verifica URL completi degli allegatoDiscussione Camera
e formato dei file (HEAD request, nessun download).

Obiettivi:
  1. Recuperare l'URL completo da dc:relation per campioni di allegati emendamento
  2. Fare HEAD request per capire il Content-Type (PDF? HTML? altro?)
  3. Fissare il formato URI legislatura: legislatura.rdf/repubblica_{N}
  4. Contare allegatoDiscussione per legislatura con URI corretto
  5. Ricostruire la catena atto → allegatoDiscussione usando rif_leg corretto

Scoperte dalla sessione precedente (diag_camera_emendamenti.py):
  - URL file sta in dc:relation (non ocd:urlFile)
  - URI legislatura corretto: http://dati.camera.it/ocd/legislatura.rdf/repubblica_{N}
  - 4.887 allegati con 'emend' nella rdfs:label su 38.675 totali
  - Gli emendamenti Camera sono bundle collettivi per seduta (non file individuali)

Usage:
  uv run explo_script/diag_camera_allegati_url.py
"""

import json
import time
import urllib.parse
import urllib.request
import urllib.error

EP = "https://dati.camera.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}


def sparql(query: str, label: str = "", timeout: int = 90) -> list[dict]:
    params = urllib.parse.urlencode({"query": query,
                                     "format": "application/sparql-results+json"})
    req = urllib.request.Request(f"{EP}?{params}", headers=H)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rows = json.loads(r.read())["results"]["bindings"]
            if label:
                print(f"  [{label}] → {len(rows)} righe")
            return rows
    except Exception as e:
        print(f"  [{label}] ERRORE: {e}")
        return []


def v(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "") or ""


def head_request(url: str) -> dict:
    """Esegue HEAD request e restituisce content-type, status, location."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "iter-legis-diag/1.0",
            "Referer": "https://www.camera.it/",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            return {
                "status": r.status,
                "content_type": r.headers.get("Content-Type", "?"),
                "content_length": r.headers.get("Content-Length", "?"),
                "final_url": r.url,
            }
    except urllib.error.HTTPError as e:
        return {"status": e.code, "content_type": "?", "content_length": "?", "final_url": url}
    except Exception as e:
        return {"status": f"ERR: {e}", "content_type": "?", "content_length": "?", "final_url": url}


# ─────────────────────────────────────────────────────────────────────────────
# PARTE 1 — URL completo da dc:relation su campione allegati emendamento
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 72)
print("PARTE 1 — URL completo (dc:relation) per allegati con label 'emend'")
print("=" * 72)

r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
SELECT DISTINCT ?all ?label ?url ?leg
WHERE {
  ?all a ocd:allegatoDiscussione ;
       rdfs:label ?label ;
       dc:relation ?url .
  OPTIONAL { ?all ocd:rif_leg ?leg }
  FILTER(CONTAINS(LCASE(?label), "emend"))
}
LIMIT 10
""", "URL completi allegati emend")

urls_to_check = []
if r:
    print(f"\n  {'Label':<50}  URL")
    print("-" * 72)
    for row in r:
        label = v(row, "label")
        url   = v(row, "url")
        leg   = v(row, "leg").split("/")[-1] if v(row, "leg") else "?"
        print(f"\n  label: {label}")
        print(f"  leg  : {leg}")
        print(f"  url  : {url}")
        urls_to_check.append(url)
else:
    print("  (nessun risultato)")

time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 2 — HEAD request per capire il formato dei file
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 2 — HEAD request sugli URL (Content-Type, dimensione)")
print("=" * 72)

seen_urls = set()
for url in urls_to_check[:5]:  # Max 5 per non sovraccaricare
    if url in seen_urls:
        continue
    seen_urls.add(url)
    print(f"\n  URL: {url[:90]}")
    info = head_request(url)
    print(f"  Status       : {info['status']}")
    print(f"  Content-Type : {info['content_type']}")
    print(f"  Content-Length: {info['content_length']} bytes")
    if info["final_url"] != url:
        print(f"  Redirect → : {info['final_url'][:90]}")
    time.sleep(0.5)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 3 — Conteggio per legislatura con URI corretto
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 3 — Conteggio allegatoDiscussione per legislatura")
print("          (URI corretto: legislatura.rdf/repubblica_{N})")
print("=" * 72)
print(f"\n  {'Leg':>4}  {'Totale':>8}  {'Con emend':>10}  {'% emend':>8}")
print("-" * 38)

for leg in range(13, 20):
    leg_uri = f"http://dati.camera.it/ocd/legislatura.rdf/repubblica_{leg}"

    # Totale allegati
    r_tot = sparql(f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(DISTINCT ?all) AS ?n)
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ocd:rif_leg <{leg_uri}> .
}}
""", f"COUNT totale Leg{leg}")
    n_tot = int(v(r_tot[0], "n")) if r_tot else -1

    # Allegati emendamento
    r_emend = sparql(f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT (COUNT(DISTINCT ?all) AS ?n)
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ocd:rif_leg <{leg_uri}> ;
       rdfs:label ?label .
  FILTER(CONTAINS(LCASE(?label), "emend"))
}}
""", f"COUNT emend Leg{leg}")
    n_emend = int(v(r_emend[0], "n")) if r_emend else -1

    pct = n_emend / n_tot * 100 if n_tot > 0 and n_emend >= 0 else 0
    print(f"  {leg:>4}  {n_tot:>8,}  {n_emend:>10,}  {pct:>7.1f}%")
    time.sleep(1.2)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 4 — Catena atto → allegatoDiscussione (URI leg corretto)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 4 — Catena atto → allegatoDiscussione (Leg17, campione)")
print("=" * 72)

leg_uri_17 = "http://dati.camera.it/ocd/legislatura.rdf/repubblica_17"

# Tenta catena via dibattito
r = sparql(f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?atto ?dibattito ?discussione ?allegato ?label
WHERE {{
  ?dibattito a ocd:dibattito ;
             ocd:rif_leg <{leg_uri_17}> ;
             ocd:rif_attoCamera ?atto ;
             ocd:rif_discussione ?discussione .
  ?discussione ocd:rif_allegatoDiscussione ?allegato .
  ?allegato rdfs:label ?label .
  FILTER(CONTAINS(LCASE(?label), "emend"))
}}
LIMIT 5
""", "catena dibattito→atto Leg17")

if r:
    print("  Catena via ocd:dibattito funziona:")
    for row in r:
        atto = v(row, "atto").split("/")[-1]
        all_ = v(row, "allegato").split("/")[-1]
        lbl  = v(row, "label")
        print(f"  atto={atto}  allegato={all_}  label={lbl[:50]}")
else:
    print("  (catena via dibattito non trovata — provo percorso alternativo)")

    # Tenta catena diretta allegatoDiscussione → atto tramite proprietà generica
    r2 = sparql(f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?allegato ?prop ?atto
WHERE {{
  ?allegato a ocd:allegatoDiscussione ;
            ocd:rif_leg <{leg_uri_17}> ;
            rdfs:label ?label ;
            ?prop ?atto .
  FILTER(CONTAINS(LCASE(?label), "emend"))
  FILTER(CONTAINS(STR(?atto), "atto") || CONTAINS(STR(?atto), "pdl") || CONTAINS(STR(?atto), "ddl"))
}}
LIMIT 10
""", "allegato → atto (generico)")

    if r2:
        print("  Collegamento allegato → atto trovato via:")
        for row in r2:
            prop = v(row, "prop").split("/")[-1]
            atto = v(row, "atto").split("/")[-1]
            print(f"  prop={prop}  atto={atto}")
    else:
        print("  (nessun collegamento diretto trovato)")
        # Mostra tutte le prop di un allegato emendamento per capire come è collegato
        r3 = sparql(f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prop ?val
WHERE {{
  <http://dati.camera.it/ocd/allegatoDiscussione.rdf/all17_17621> ?prop ?val .
}}
""", "tutte props di all17_17621")
        if r3:
            print("\n  Tutte le proprietà di all17_17621 (allegato emend campione):")
            for row in r3:
                prop = v(row, "prop")
                val  = v(row, "val")
                print(f"  {prop.split('/')[-1]:<30} = {val[:80]}")

time.sleep(1)

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 5 — Trova il collegamento inverso: chi punta all'allegatoDiscussione?
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 5 — Chi punta a un allegatoDiscussione? (link inverso)")
print("=" * 72)

r = sparql("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT DISTINCT ?soggetto ?tipo ?prop
WHERE {
  ?soggetto ?prop <http://dati.camera.it/ocd/allegatoDiscussione.rdf/all17_17621> .
  OPTIONAL { ?soggetto a ?tipo }
}
LIMIT 10
""", "link inverso all17_17621")

if r:
    print("  Entità che puntano all'allegato all17_17621:")
    for row in r:
        sogg = v(row, "soggetto").split("/")[-1]
        tipo = v(row, "tipo").split("/")[-1] if v(row, "tipo") else "?"
        prop = v(row, "prop").split("/")[-1]
        print(f"  soggetto={sogg}  tipo={tipo}  via prop={prop}")
else:
    print("  (nessun link inverso trovato)")

# ─────────────────────────────────────────────────────────────────────────────
# PARTE 6 — GET sul servizio .ashx per vedere i 269 bytes restituiti
#            (Content-Type: text/plain → probabile URL al documento reale)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 72)
print("PARTE 6 — GET su URL .ashx: cosa contengono i 269 bytes?")
print("=" * 72)

# Usa il primo URL trovato in Parte 1
test_url = (
    "http://documenti.camera.it/apps/commonServices/getDocumento.ashx"
    "?sezione=bollettini&tipoDoc=allegato&idLegislatura=17"
    "&anno=2014&mese=05&giorno=14&idcommissione=0108"
    "&pagina=data.20140514.com0108.allegati.all00010"
    "&ancora=data.20140514.com0108.allegati.all00010"
)

print(f"\n  GET: {test_url[:90]}...")
try:
    req = urllib.request.Request(test_url, headers={
        "User-Agent": "iter-legis-diag/1.0",
        "Referer": "https://www.camera.it/",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read()
        ct   = r.headers.get("Content-Type", "?")
        print(f"  Status       : {r.status}")
        print(f"  Content-Type : {ct}")
        print(f"  Bytes letti  : {len(body)}")
        print(f"  Contenuto    : {body[:500]}")
except Exception as e:
    print(f"  ERRORE GET: {e}")

print()
print("=" * 72)
print("Fine diagnostica URL allegati Camera")
print("=" * 72)
print()
print("INTERPRETAZIONE:")
print("  - PARTE 1+2: Content-Type text/plain (269 bytes) → non è il PDF diretto")
print("    → PARTE 6 mostra cosa contengono quei 269 bytes")
print("    Se è una URL: il servizio funziona come redirect testuale (fetch quella URL)")
print("    Se è HTML:    serve scraping della pagina")
print("    Se è PDF raw: il Content-Type era sbagliato")
print("  - PARTE 3: Leg13-15 = 0 allegati (pre-digitale); Leg16-19 coperti")
print("  - PARTE 4+5: catena atto→allegato confermata via ocd:dibattito")
