#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["requests"]
# ///
"""
diag_camera_sparql.py — Diagnostica struttura triplestore Camera dei Deputati.
/ Diagnostic exploration of the Camera dei Deputati SPARQL triplestore.

Domande chiave / Key questions:
  1. Top classi nel triplestore Camera
  2. Conta ocd:atto per legislatura (pattern URI legislatura)
  3. Verifica cap paginazione (come Virtuoso Senato?)
  4. Tutte le proprietà di un atto campione (Leg17/18)
  5. Proprietà numeriche/ID per keyset pagination
  6. Coverage versioneTestoAtto (URL PDF testi presentati)
  7. Come si collegano gli emendamenti (allegatoDiscussione)
  8. Link Camera→Senato via ocd:trasmissione / ocd:rif_attoSenato
  9. Tipo atto / natura (DDL, PDL, DL, ecc.)
 10. Campi data e stato iter

Usage:
  uv run explo_script/diag_camera_sparql.py
  uv run explo_script/diag_camera_sparql.py --leg 17
  uv run explo_script/diag_camera_sparql.py --section 4   # only section 4
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

EP  = "https://dati.camera.it/sparql"
OCD = "http://dati.camera.it/ocd/"

# Known from test_camera_urls.py (2026-05-27): legislature URI pattern.
def leg_uri(n: int) -> str:
    return f"{OCD}legislatura.rdf/repubblica_{n}"


HEADERS = {
    "Accept":     "application/sparql-results+json",
    "User-Agent": "iter-legis-diag/1.0",
}


def q(query: str, label: str = "", timeout: int = 60, silent: bool = False) -> list[dict]:
    params = urllib.parse.urlencode({
        "query":  query,
        "format": "application/sparql-results+json",
    })
    req = urllib.request.Request(f"{EP}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            rows = data.get("results", {}).get("bindings", [])
            if not silent:
                print(f"  [{label}] → {len(rows)} righe")
            return rows
    except urllib.error.HTTPError as e:
        body = e.read(200).decode("utf-8", errors="replace")
        print(f"  [{label}] HTTP {e.code}: {body[:120]}")
        return []
    except Exception as e:
        print(f"  [{label}] ERRORE: {e}")
        return []


def v(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "")


def sep(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


# ── 1. Top classi nel triplestore ─────────────────────────────────────────

def section_1() -> None:
    sep("1. TOP 20 classi nel triplestore Camera")
    rows = q("""
SELECT ?cls (COUNT(*) AS ?n)
WHERE { ?s a ?cls }
GROUP BY ?cls ORDER BY DESC(?n) LIMIT 20
""", "top-classi", timeout=90)
    for r in rows:
        print(f"    {v(r,'n'):>10}  {v(r,'cls')}")
    time.sleep(1)


# ── 2. Count ocd:atto per legislatura ─────────────────────────────────────

def section_2(legs: list[int]) -> None:
    sep("2. COUNT ocd:atto per legislatura")
    print("  (verifica se ocd:atto è la classe DDL equivalente a osr:Ddl)\n")
    for leg in legs:
        leg_u = leg_uri(leg)
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(*) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
""", f"Leg{leg} COUNT")
        n = v(rows[0], "n") if rows else "ERR"
        print(f"    Leg{leg}: {n}")
        time.sleep(0.5)

    # Also count total without leg filter to detect if rif_leg is needed
    rows_tot = q("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT (COUNT(*) AS ?n)
WHERE { ?s a ocd:atto }
""", "COUNT totale ocd:atto")
    print(f"\n  Totale ocd:atto senza filtro leg: {v(rows_tot[0], 'n') if rows_tot else 'ERR'}")
    time.sleep(1)


# ── 3. Test cap paginazione (LIMIT/OFFSET) ────────────────────────────────

def section_3() -> None:
    sep("3. Test cap paginazione — LIMIT/OFFSET")
    print("  Testa OFFSET 0, 500, 1000, 5000, 9000, 10000 su Leg17")
    leg_u = leg_uri(17)

    for offset in [0, 500, 1000, 5000, 9000, 10000]:
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
ORDER BY ?atto
LIMIT 5 OFFSET {offset}
""", f"OFFSET {offset}", silent=True)
        status = f"{len(rows)} righe" if rows else "VUOTO/ERRORE"
        first  = v(rows[0], "atto").split("/")[-1] if rows else ""
        print(f"    OFFSET {offset:>6}: {status}  first={first}")
        time.sleep(0.3)
    time.sleep(1)


# ── 4. Tutte le proprietà di un atto campione ─────────────────────────────

def section_4(leg: int = 17) -> None:
    sep(f"4. Tutte le proprietà di un atto campione (Leg{leg})")
    leg_u = leg_uri(leg)

    rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
LIMIT 5
""", f"campione Leg{leg}")
    if not rows:
        print("  ⚠️ Nessun atto trovato.")
        return

    for sample_row in rows[:3]:
        atto_uri = v(sample_row, "atto")
        print(f"\n  --- URI: {atto_uri} ---")
        props = q(f"SELECT ?p ?o WHERE {{ <{atto_uri}> ?p ?o }}", "props", silent=True)
        for r in props:
            p_short = v(r, "p").split("/")[-1].split("#")[-1]
            o       = v(r, "o")
            print(f"    {p_short:<35}  {o[:90]}")
        time.sleep(0.5)
    time.sleep(1)


# ── 5. Proprietà usabili per keyset pagination ────────────────────────────

def section_5(leg: int = 17) -> None:
    sep(f"5. Proprietà ID/numeriche per keyset pagination (Leg{leg})")
    leg_u = leg_uri(leg)

    # Check for ocd:id, ocd:numero, ocd:idAtto, dc:identifier equivalents
    candidates = [
        ("ocd:id",             f"<{OCD}id>"),
        ("ocd:idAtto",         f"<{OCD}idAtto>"),
        ("ocd:numero",         f"<{OCD}numero>"),
        ("ocd:numeroAtto",     f"<{OCD}numeroAtto>"),
        ("dc:identifier",      "<http://purl.org/dc/elements/1.1/identifier>"),
        ("dcterms:identifier", "<http://purl.org/dc/terms/identifier>"),
        ("rdfs:label",         "<http://www.w3.org/2000/01/rdf-schema#label>"),
    ]

    for name, pred in candidates:
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto ?val
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
}}
LIMIT 3
""", f"{name}", silent=True)
        if rows:
            examples = [v(r, "val")[:50] for r in rows]
            print(f"  ✅ {name:<25}  esempi: {examples}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.3)

    # Check what the URI itself looks like (for URI-based keyset)
    rows_uri = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
ORDER BY ?atto LIMIT 5
""", "ORDER BY URI", silent=True)
    print(f"\n  Prime 5 URI ordinate di ocd:atto Leg{leg}:")
    for r in rows_uri:
        print(f"    {v(r,'atto')}")
    time.sleep(1)


# ── 6. Coverage versioneTestoAtto (URL PDF) ───────────────────────────────

def section_6(legs: list[int]) -> None:
    sep("6. Coverage versioneTestoAtto — URL PDF testi presentati")

    for leg in legs:
        leg_u = leg_uri(leg)

        # Count atti with rif_versioneTestoAtto
        rows_vta = q(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_versioneTestoAtto ?vta .
}}
""", f"Leg{leg} atti con rif_vta")

        # Count vta with isReferencedBy URL
        rows_url = q(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?vta) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_versioneTestoAtto ?vta .
  ?vta <http://purl.org/dc/elements/1.1/isReferencedBy> ?url .
}}
""", f"Leg{leg} vta con URL")

        n_vta = v(rows_vta[0], "n") if rows_vta else "ERR"
        n_url = v(rows_url[0], "n") if rows_url else "ERR"
        print(f"    Leg{leg}: atti con vta={n_vta}  vta con URL={n_url}")
        time.sleep(0.5)

    # Sample one URL for Leg17
    leg_u17 = leg_uri(17)
    rows_sample = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto ?vta ?url
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u17}> ;
        ocd:rif_versioneTestoAtto ?vta .
  ?vta <http://purl.org/dc/elements/1.1/isReferencedBy> ?url .
}}
LIMIT 3
""", "campione URL Leg17", silent=True)
    print(f"\n  Campione URL testi Leg17:")
    for r in rows_sample:
        print(f"    atto={v(r,'atto').split('/')[-1]}  url={v(r,'url')[:80]}")

    # Also check dc:title / dcterms:title on versioneTestoAtto
    if rows_sample:
        vta_uri = v(rows_sample[0], "vta")
        rows_vta_props = q(f"SELECT ?p ?o WHERE {{ <{vta_uri}> ?p ?o }}", "vta props", silent=True)
        print(f"\n  Proprietà di una versioneTestoAtto ({vta_uri.split('/')[-1]}):")
        for r in rows_vta_props:
            p = v(r, "p").split("/")[-1].split("#")[-1]
            print(f"    {p:<35}  {v(r,'o')[:80]}")
    time.sleep(1)


# ── 7. Emendamenti — allegatoDiscussione ─────────────────────────────────

def section_7(legs: list[int]) -> None:
    sep("7. Emendamenti — ocd:allegatoDiscussione e linking")

    for leg in legs:
        leg_u = leg_uri(leg)

        rows_all = q(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?all) AS ?n)
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ocd:rif_leg <{leg_u}> .
}}
""", f"Leg{leg} allegatoDiscussione COUNT")
        print(f"    Leg{leg}: allegatoDiscussione={v(rows_all[0], 'n') if rows_all else 'ERR'}")
        time.sleep(0.5)

    # Sample allegatoDiscussione Leg17 — all properties
    leg_u17 = leg_uri(17)
    rows_sample = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?all
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ocd:rif_leg <{leg_u17}> .
}}
LIMIT 3
""", "campione allegatoDiscussione Leg17", silent=True)

    if rows_sample:
        print(f"\n  Proprietà di allegatoDiscussione campione (Leg17):")
        for sr in rows_sample[:2]:
            all_uri = v(sr, "all")
            print(f"\n  --- {all_uri.split('/')[-1]} ---")
            props = q(f"SELECT ?p ?o WHERE {{ <{all_uri}> ?p ?o }}", "props", silent=True)
            for r in props:
                p = v(r, "p").split("/")[-1].split("#")[-1]
                print(f"    {p:<35}  {v(r,'o')[:80]}")
            time.sleep(0.3)

    # Check if there's a direct atto→allegatoDiscussione link
    rows_link = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?atto ?all ?label
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u17}> ;
        ?p ?all .
  ?all a ocd:allegatoDiscussione .
  OPTIONAL {{ ?all <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
}}
LIMIT 5
""", "atto→allegatoDiscussione direct link Leg17", silent=True)
    if rows_link:
        print(f"\n  ✅ Link diretto atto→allegatoDiscussione trovato:")
        for r in rows_link:
            print(f"    atto={v(r,'atto').split('/')[-1]}  all={v(r,'all').split('/')[-1]}  label={v(r,'label')[:60]}")
    else:
        print("\n  ✗ Nessun link diretto atto→allegatoDiscussione (join inverso necessario?)")
        # Try inverse: allegatoDiscussione→atto
        rows_inv = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?all ?atto ?label
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ocd:rif_leg <{leg_u17}> ;
       ?p ?atto .
  ?atto a ocd:atto .
  OPTIONAL {{ ?all <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
}}
LIMIT 5
""", "allegatoDiscussione→atto inverse Leg17", silent=True)
        if rows_inv:
            print(f"  ✅ Link inverso allegatoDiscussione→atto trovato:")
            for r in rows_inv:
                print(f"    all={v(r,'all').split('/')[-1]}  atto={v(r,'atto').split('/')[-1]}  label={v(r,'label')[:60]}")
        else:
            print("  ✗ Nessun link inverso trovato — isola?")
    time.sleep(1)


# ── 8. Link Camera→Senato (trasmissione / rif_attoSenato) ────────────────

def section_8() -> None:
    sep("8. Link Camera→Senato — ocd:trasmissione e ocd:rif_attoSenato")

    rows = q("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?tr ?rif_sen ?label
WHERE {
  ?tr a ocd:trasmissione ;
      ocd:rif_attoSenato ?rif_sen .
  OPTIONAL { ?tr <http://www.w3.org/2000/01/rdf-schema#label> ?label }
}
LIMIT 10
""", "campione ocd:trasmissione", silent=True)

    if rows:
        print(f"  ✅ ocd:trasmissione con ocd:rif_attoSenato trovato ({len(rows)} campioni):")
        for r in rows:
            rs  = v(r, "rif_sen")
            lab = v(r, "label")[:50]
            print(f"    rif_attoSenato={rs[:70]}  label={lab}")

        # Check if the rif_attoSenato points to dati.senato.it URIs
        first_rs = v(rows[0], "rif_sen")
        if "senato.it" in first_rs:
            print(f"\n  → URI Senato confermato: collegamento diretto via SPARQL ✅")
        else:
            print(f"\n  → Formato non Senato URI: {first_rs[:80]}")
    else:
        print("  ✗ ocd:trasmissione non trovata o senza ocd:rif_attoSenato")

    # Check from atto side
    rows_atto = q("""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?atto ?tr ?rif_sen
WHERE {
  ?atto a ocd:atto ;
        ocd:rif_trasmissione ?tr .
  ?tr ocd:rif_attoSenato ?rif_sen .
}
LIMIT 5
""", "atto→trasmissione→senato", silent=True)
    if rows_atto:
        print(f"\n  ✅ atto→rif_trasmissione→rif_attoSenato funziona:")
        for r in rows_atto:
            print(f"    atto={v(r,'atto').split('/')[-1]}  rif_sen={v(r,'rif_sen')[:70]}")
    else:
        print(f"\n  ✗ Catena atto→rif_trasmissione→rif_attoSenato non funziona")
    time.sleep(1)


# ── 9. Tipo atto / natura ────────────────────────────────────────────────

def section_9(legs: list[int]) -> None:
    sep("9. Tipo atto / natura — distribuzione per legislatura")

    leg_u17 = leg_uri(17)

    # Cerca proprietà legate al tipo atto
    type_candidates = [
        ("ocd:tipoAtto",          f"<{OCD}tipoAtto>"),
        ("ocd:natura",            f"<{OCD}natura>"),
        ("ocd:tipo",              f"<{OCD}tipo>"),
        ("ocd:rif_tipoAtto",      f"<{OCD}rif_tipoAtto>"),
        ("dc:type",               "<http://purl.org/dc/elements/1.1/type>"),
        ("dcterms:type",          "<http://purl.org/dc/terms/type>"),
        ("rdfs:type / rdf:type",  "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"),
    ]

    print("  Proprietà tipo su ocd:atto Leg17:")
    for name, pred in type_candidates:
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?val (COUNT(*) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u17}> ;
        {pred} ?val .
}}
GROUP BY ?val ORDER BY DESC(?n) LIMIT 5
""", f"{name}", silent=True)
        if rows and v(rows[0], "val") not in ("http://dati.camera.it/ocd/atto", ""):
            print(f"  ✅ {name:<30}  valori: {[v(r,'val').split('/')[-1][:30]+' n='+v(r,'n') for r in rows[:4]]}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.3)

    # Check ocd:rif_tipoAtto as a linked entity
    rows_tipo = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?tipo ?label (COUNT(?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u17}> ;
        ocd:rif_tipoAtto ?tipo .
  OPTIONAL {{ ?tipo <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
}}
GROUP BY ?tipo ?label ORDER BY DESC(?n)
""", "rif_tipoAtto aggregato Leg17", silent=True)
    if rows_tipo:
        print(f"\n  Distribuzione ocd:rif_tipoAtto Leg17:")
        for r in rows_tipo:
            lbl = v(r, "label") or v(r, "tipo").split("/")[-1]
            print(f"    {v(r,'n'):>6}  {lbl[:60]}")
    time.sleep(1)


# ── 10. Campi data e stato iter ─────────────────────────────────────────

def section_10(leg: int = 17) -> None:
    sep(f"10. Campi data e stato iter (Leg{leg})")
    leg_u = leg_uri(leg)

    date_candidates = [
        ("ocd:dataPresentazione",   f"<{OCD}dataPresentazione>"),
        ("ocd:dataRicezione",       f"<{OCD}dataRicezione>"),
        ("ocd:dataApprovazione",    f"<{OCD}dataApprovazione>"),
        ("dc:date",                 "<http://purl.org/dc/elements/1.1/date>"),
        ("dcterms:date",            "<http://purl.org/dc/terms/date>"),
        ("dcterms:created",         "<http://purl.org/dc/terms/created>"),
        ("dcterms:modified",        "<http://purl.org/dc/terms/modified>"),
    ]
    stato_candidates = [
        ("ocd:statoIter",       f"<{OCD}statoIter>"),
        ("ocd:stato",           f"<{OCD}stato>"),
        ("ocd:rif_statoIter",   f"<{OCD}rif_statoIter>"),
        ("ocd:rif_stato",       f"<{OCD}rif_stato>"),
    ]

    print("  Campi data:")
    for name, pred in date_candidates:
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?val
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
}}
LIMIT 3
""", name, silent=True)
        if rows:
            print(f"  ✅ {name:<30}  esempi: {[v(r,'val')[:30] for r in rows]}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.2)

    print("\n  Campi stato:")
    for name, pred in stato_candidates:
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?val (COUNT(*) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
}}
GROUP BY ?val ORDER BY DESC(?n) LIMIT 5
""", name, silent=True)
        if rows:
            vals = [v(r,"val").split("/")[-1][:25]+" n="+v(r,"n") for r in rows[:4]]
            print(f"  ✅ {name:<30}  {vals}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.2)

    # Stato via rif_iter (linked entity)
    rows_iter = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?stato ?label (COUNT(?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_iter ?iter .
  ?iter ?p ?stato .
  OPTIONAL {{ ?stato <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
  FILTER(CONTAINS(STR(?p), "stato") || CONTAINS(STR(?p), "iter"))
}}
GROUP BY ?stato ?label ORDER BY DESC(?n) LIMIT 10
""", "rif_iter/stato Leg17", silent=True)
    if rows_iter:
        print(f"\n  Distribuzione stati via ocd:rif_iter:")
        for r in rows_iter:
            lbl = v(r, "label") or v(r, "stato").split("/")[-1]
            print(f"    {v(r,'n'):>6}  {lbl[:60]}")
    time.sleep(1)


# ── 11. Titolo e proprietà testuali ──────────────────────────────────────

def section_11(leg: int = 17) -> None:
    sep(f"11. Proprietà testuali — titolo, numero, iniziativa (Leg{leg})")
    leg_u = leg_uri(leg)

    text_candidates = [
        ("ocd:titolo",            f"<{OCD}titolo>"),
        ("ocd:numero",            f"<{OCD}numero>"),
        ("ocd:iniziativa",        f"<{OCD}iniziativa>"),
        ("ocd:rif_iniziativa",    f"<{OCD}rif_iniziativa>"),
        ("dc:title",              "<http://purl.org/dc/elements/1.1/title>"),
        ("dcterms:title",         "<http://purl.org/dc/terms/title>"),
        ("dc:subject",            "<http://purl.org/dc/elements/1.1/subject>"),
        ("rdfs:label",            "<http://www.w3.org/2000/01/rdf-schema#label>"),
        ("ocd:descr_iniziativa",  f"<{OCD}descr_iniziativa>"),
    ]

    for name, pred in text_candidates:
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?val
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
}}
LIMIT 3
""", name, silent=True)
        if rows:
            print(f"  ✅ {name:<30}  es: {v(rows[0],'val')[:80]!r}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.2)
    time.sleep(1)


# ── 12. Proponenti / firmatari ─────────────────────────────────────────

def section_12(leg: int = 17) -> None:
    sep(f"12. Proponenti / firmatari (Leg{leg})")
    leg_u = leg_uri(leg)

    prop_candidates = [
        ("ocd:rif_proponente",   f"<{OCD}rif_proponente>"),
        ("ocd:rif_firmatario",   f"<{OCD}rif_firmatario>"),
        ("ocd:proponente",       f"<{OCD}proponente>"),
        ("ocd:rif_presentatore", f"<{OCD}rif_presentatore>"),
        ("dc:creator",           "<http://purl.org/dc/elements/1.1/creator>"),
        ("dcterms:creator",      "<http://purl.org/dc/terms/creator>"),
    ]
    for name, pred in prop_candidates:
        rows = q(f"""
PREFIX ocd: <{OCD}>
SELECT ?val
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
}}
LIMIT 3
""", name, silent=True)
        if rows:
            print(f"  ✅ {name:<30}  es: {v(rows[0],'val')[:80]!r}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.2)

    # Check class ocd:presentatore
    rows_pres = q(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(*) AS ?n)
WHERE {{ ?s a ocd:presentatore }}
""", "ocd:presentatore COUNT", silent=True)
    print(f"\n  Totale istanze ocd:presentatore: {v(rows_pres[0],'n') if rows_pres else 'ERR'}")
    time.sleep(1)


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnostica triplestore Camera dei Deputati."
    )
    parser.add_argument("--leg",     type=int, default=17,
                        help="Legislatura campione per sezioni dettagliate (default: 17)")
    parser.add_argument("--section", type=int, default=0,
                        help="Esegui solo questa sezione (0=tutte)")
    args = parser.parse_args()

    legs_all = [13, 14, 15, 16, 17, 18, 19]
    legs_sample = [15, 17, 18, 19]   # representative sample to avoid too many requests

    print("diag_camera_sparql.py — Diagnostica triplestore Camera dei Deputati")
    print(f"Endpoint: {EP}")
    print(f"Legislatura campione: Leg{args.leg}")
    print()

    run = args.section

    if run in (0, 1):  section_1()
    if run in (0, 2):  section_2(legs_all)
    if run in (0, 3):  section_3()
    if run in (0, 4):  section_4(args.leg)
    if run in (0, 5):  section_5(args.leg)
    if run in (0, 6):  section_6(legs_sample)
    if run in (0, 7):  section_7(legs_sample)
    if run in (0, 8):  section_8()
    if run in (0, 9):  section_9(legs_all)
    if run in (0, 10): section_10(args.leg)
    if run in (0, 11): section_11(args.leg)
    if run in (0, 12): section_12(args.leg)

    print(f"\n{'=' * 70}")
    print("✅ Diagnostica completata.")


if __name__ == "__main__":
    main()
