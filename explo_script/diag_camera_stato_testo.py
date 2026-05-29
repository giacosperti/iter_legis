#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
diag_camera_stato_testo.py — Esplora la struttura di ocd:statoIter e dc:relation
su ocd:atto nel triplestore Camera dei Deputati.

Domande:
  P1. ocd:statoIter — che proprietà ha? (label testuale? data? tipo?)
       Serve per estrarre lo stato iter leggibile e la sua data in atti_camera.parquet.

  P2. dc:relation su ocd:atto — quante URL per atto? Pattern dei valori?
       L'analisi diag_camera_atti.py ha rilevato avg 3 URL per atto — dobbiamo capire
       se una è sempre il PDF del testo presentato e come distinguerle.

  P3. ocd:versioneTestoAtto — che proprietà ha? Contiene l'URL PDF o solo metadati?
       N atti con rif_versioneTestoAtto == N atti con dc:relation (entrambi 4850 su Leg17).
       Il sospetto è che dc:relation sull'atto sia la denormalizzazione dell'URL
       contenuto in versioneTestoAtto.

  P4. ocd:primo_firmatario — URI o letterale? Come si collega all'anagrafica?
       Serve per il join futuro con t_deputati.

  P5. ocd:rif_natura — label testuale della natura dell'atto?
       L'URI è già estratta (es. natura.rdf/proposta_legge_ordinaria), ma serve
       il label per rendere la colonna leggibile.

  P6. COUNT dc:relation per atto — distribuzione (1, 2, 3, …?).
       Capire se "3 in media" è una mediana o se ci sono outlier.

Endpoint: https://dati.camera.it/sparql
Prefisso:  ocd: <http://dati.camera.it/ocd/>

Usage:
  python3 explo_script/diag_camera_stato_testo.py
  python3 explo_script/diag_camera_stato_testo.py --leg 18
  python3 explo_script/diag_camera_stato_testo.py --section 2
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request

EP  = "https://dati.camera.it/sparql"
OCD = "http://dati.camera.it/ocd/"
DC  = "http://purl.org/dc/elements/1.1/"
DCT = "http://purl.org/dc/terms/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"

HEADERS = {
    "Accept":     "application/sparql-results+json",
    "User-Agent": "iter-legis-diag/1.0 (stato_testo)",
}


def leg_uri(n: int) -> str:
    return f"{OCD}legislatura.rdf/repubblica_{n}"


def sparql(query: str, label: str = "", timeout: int = 90,
           silent: bool = False) -> list[dict]:
    params = urllib.parse.urlencode({
        "query":  query,
        "format": "application/sparql-results+json",
    })
    req = urllib.request.Request(f"{EP}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("results", {}).get("bindings", [])
            if not silent:
                print(f"  [{label}] → {len(rows)} righe")
            return rows
    except urllib.error.HTTPError as e:
        body = e.read(300).decode("utf-8", errors="replace")
        print(f"  [{label}] HTTP {e.code}: {body[:150]}")
        return []
    except Exception as e:
        print(f"  [{label}] ERRORE: {e}")
        return []


def val(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "") or ""


def short(uri: str) -> str:
    """Shorten a URI for display."""
    return (uri.replace(OCD, "ocd:")
               .replace(DC,  "dc:")
               .replace(DCT, "dcterms:")
               .replace(RDF, "rdf:")
               .replace(RDFS, "rdfs:"))


def sep(n: int, title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  P{n}. {title}")
    print('=' * 72)


# ── P1. Struttura ocd:statoIter ────────────────────────────────────────────

def p1_stato_iter(leg: int) -> None:
    """Explore all properties of ocd:statoIter instances linked from ocd:atto.

    Goal: find label text (human-readable status like "Approvato"), date, and
    any sequential ID usable to identify the "most recent" state.
    """
    sep(1, "Struttura ocd:statoIter (label, data, tipo)")
    leg_u = leg_uri(leg)

    # Fetch a sample of statoIter URIs from Leg{leg}
    rows_sample = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT DISTINCT ?atto ?si
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_statoIter ?si .
}}
ORDER BY ?atto ?si
LIMIT 6
""", f"campione statoIter Leg{leg}", silent=True)

    if not rows_sample:
        print("  ⚠️ Nessun statoIter trovato.")
        return

    # Group by atto (show one atto with multiple stati, then dump each si)
    seen_atti: dict[str, list[str]] = {}
    for r in rows_sample:
        a = val(r, "atto")
        s = val(r, "si")
        seen_atti.setdefault(a, []).append(s)

    print(f"\n  Atti campione con i loro statoIter:")
    for atto, stati in list(seen_atti.items())[:3]:
        atto_s = atto.split("/")[-1]
        stati_s = [s.split("/")[-1] for s in stati]
        print(f"    {atto_s}: {stati_s}")

    # Dump all properties of the first 3 statoIter URIs
    all_si_uris = [val(r, "si") for r in rows_sample][:4]
    seen_si: set[str] = set()

    print(f"\n  Dump proprietà dei primi statoIter:")
    for si_uri in all_si_uris:
        if si_uri in seen_si:
            continue
        seen_si.add(si_uri)

        props = sparql(f"SELECT ?p ?o WHERE {{ <{si_uri}> ?p ?o }}",
                       "props", silent=True)
        print(f"\n  ── {si_uri.split('/')[-1]} ──")
        for r in props:
            p = short(val(r, "p"))
            o = val(r, "o")
            print(f"    {p:<40}  {o[:75]}")
        time.sleep(0.3)

    # Check: is there a property with "stato" or "label" that gives the text?
    print(f"\n  Distribuzione valori rdfs:label su ocd:statoIter (Leg{leg}):")
    rows_labels = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX rdfs: <{RDFS}>
SELECT ?label (COUNT(DISTINCT ?si) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_statoIter ?si .
  ?si rdfs:label ?label .
}}
GROUP BY ?label
ORDER BY DESC(?n)
LIMIT 20
""", "labels statoIter", silent=True)

    if rows_labels:
        for r in rows_labels:
            print(f"    {val(r,'n'):>6}  {val(r,'label')[:60]}")
    else:
        print("  (rdfs:label non disponibile su ocd:statoIter)")

    # Try dc:title and dc:description on statoIter
    for pred_name, pred_uri in [("dc:title", f"{DC}title"),
                                  ("dc:description", f"{DC}description"),
                                  ("dc:type", f"{DC}type")]:
        rows_p = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT DISTINCT ?v
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_statoIter ?si .
  ?si <{pred_uri}> ?v .
}}
LIMIT 5
""", pred_name, silent=True)
        if rows_p:
            print(f"  ✅ ocd:statoIter → {pred_name}: {[val(r,'v')[:40] for r in rows_p]}")
        else:
            print(f"  ✗  ocd:statoIter → {pred_name}: non disponibile")
        time.sleep(0.2)

    # Check if statoIter has a date property
    print(f"\n  Cercando proprietà data su ocd:statoIter:")
    date_preds = [
        ("dc:date",          f"{DC}date"),
        ("dcterms:date",     f"{DCT}date"),
        ("dcterms:created",  f"{DCT}created"),
        ("dcterms:modified", f"{DCT}modified"),
        ("ods:modified",     "http://lod.xdams.org/ontologies/ods/modified"),
    ]
    for name, pred in date_preds:
        rows_d = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT ?v
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_statoIter ?si .
  ?si <{pred}> ?v .
}}
LIMIT 3
""", name, silent=True)
        if rows_d:
            print(f"  ✅ {name:<25}  esempi: {[val(r,'v')[:30] for r in rows_d]}")
        else:
            print(f"  ✗  {name}")
        time.sleep(0.2)

    time.sleep(1)


# ── P2. dc:relation su ocd:atto — pattern e molteplicità ──────────────────

def p2_dc_relation(leg: int) -> None:
    """Examine all dc:relation values on a sample of atti.

    Goal: understand how many URLs per atto, whether one is always the 'primary'
    presented text PDF, and whether there's a distinguishing pattern in the URLs.
    """
    sep(2, f"dc:relation su ocd:atto — molteplicità e pattern URL (Leg{leg})")
    leg_u = leg_uri(leg)

    # Fetch 5 atti that have exactly 1 dc:relation
    rows_1 = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?atto ?url
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        dc:relation ?url .
}}
ORDER BY xsd:integer(?id)
LIMIT 8
""", "campione dc:relation", silent=True)

    if not rows_1:
        print("  ⚠️ Nessun risultato — dc:relation non trovato.")
        return

    # Group by atto
    atto_urls: dict[str, list[str]] = {}
    for r in rows_1:
        a = val(r, "atto").split("/")[-1]
        u = val(r, "url")
        atto_urls.setdefault(a, []).append(u)

    print(f"\n  URL per atto (campione):")
    for atto, urls in list(atto_urls.items())[:5]:
        print(f"\n  [{atto}]  ({len(urls)} URL)")
        for u in urls:
            # classify the URL pattern
            u_lower = u.lower()
            if "pdf" in u_lower:
                tag = "PDF"
            elif "htm" in u_lower:
                tag = "HTML"
            elif "xml" in u_lower:
                tag = "XML"
            else:
                tag = "?"
            print(f"    [{tag}] {u[:85]}")

    time.sleep(1)

    # Now: fetch an atto with MULTIPLE dc:relation to understand the patterns
    print(f"\n  Atti con più dc:relation (Leg{leg} — cercando atti con 3+ URL):")
    rows_multi = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?atto (COUNT(?url) AS ?n_url)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        dc:relation ?url .
}}
GROUP BY ?atto
HAVING (COUNT(?url) > 2)
ORDER BY DESC(COUNT(?url))
LIMIT 5
""", "atti con 3+ dc:relation", silent=True)

    if rows_multi:
        for r in rows_multi:
            atto_id = val(r, "atto").split("/")[-1]
            n_url   = val(r, "n_url")
            print(f"    {atto_id}: {n_url} URL")

            # Dump all URLs for this atto
            atto_uri = val(r, "atto")
            rows_urls = sparql(f"""
PREFIX dc: <{DC}>
SELECT ?url
WHERE {{ <{atto_uri}> dc:relation ?url }}
""", "URLs", silent=True)
            for ru in rows_urls:
                u = val(ru, "url")
                tag = "PDF" if "pdf" in u.lower() else ("HTML" if "htm" in u.lower() else "?")
                print(f"      [{tag}] {u[:85]}")
            time.sleep(0.3)
    else:
        print("  (nessun atto con 3+ URL trovato — struttura GROUP BY non supportata?)")

    time.sleep(1)

    # Distribution: how many atti have 1, 2, 3 dc:relation?
    print(f"\n  Distribuzione n. dc:relation per atto (Leg{leg}):")
    rows_dist = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT ?n_url (COUNT(DISTINCT ?atto) AS ?n_atti)
WHERE {{
  SELECT DISTINCT ?atto (COUNT(?url) AS ?n_url)
  WHERE {{
    ?atto a ocd:atto ;
          ocd:rif_leg <{leg_u}> ;
          dc:relation ?url .
  }}
  GROUP BY ?atto
}}
GROUP BY ?n_url
ORDER BY ?n_url
""", "distribuzione n URL", silent=True)

    if rows_dist:
        for r in rows_dist:
            n_url  = val(r, "n_url")
            n_atti = val(r, "n_atti")
            print(f"    {n_url} URL: {n_atti:>6} atti")
    else:
        print("  (query distribuzione non supportata — nested SELECT)")

    time.sleep(1)


# ── P3. Struttura ocd:versioneTestoAtto ───────────────────────────────────

def p3_versione_testo(leg: int) -> None:
    """Explore ocd:versioneTestoAtto structure.

    From diag_camera_atti.py: both ocd:rif_versioneTestoAtto and dc:relation
    cover 4850 atti with the same total value count (14560) in Leg17.
    Hypothesis: dc:relation on the atto is a shortcut — the same URLs also appear
    on ocd:versioneTestoAtto via its own dc:relation or dc:isReferencedBy.
    """
    sep(3, f"Struttura ocd:versioneTestoAtto (Leg{leg})")
    leg_u = leg_uri(leg)

    # Fetch a sample versioneTestoAtto URI
    rows_vta = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT DISTINCT ?atto ?vta
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_versioneTestoAtto ?vta .
}}
ORDER BY ?atto
LIMIT 4
""", "campione vta", silent=True)

    if not rows_vta:
        print("  ⚠️ Nessun versioneTestoAtto trovato.")
        return

    # For each sample: dump all properties
    seen_vta: set[str] = set()
    for sr in rows_vta[:3]:
        vta_uri = val(sr, "vta")
        if vta_uri in seen_vta:
            continue
        seen_vta.add(vta_uri)

        atto_id = val(sr, "atto").split("/")[-1]
        print(f"\n  ── {vta_uri.split('/')[-1]}  (da atto {atto_id}) ──")

        props = sparql(f"SELECT ?p ?o WHERE {{ <{vta_uri}> ?p ?o }}",
                       "dump vta", silent=True)
        for r in props:
            p = short(val(r, "p"))
            o = val(r, "o")
            print(f"    {p:<40}  {o[:80]}")
        time.sleep(0.4)

    # Check: does vta have dc:relation with the same URL as the atto?
    print(f"\n  Verifica: dc:relation su atto == dc:relation su vta?")
    rows_check = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?atto ?url_atto ?vta ?url_vta
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        dc:relation ?url_atto ;
        ocd:rif_versioneTestoAtto ?vta .
  ?vta dc:relation ?url_vta .
}}
LIMIT 4
""", "confronto URL atto vs vta", silent=True)

    if rows_check:
        for r in rows_check:
            atto_id = val(r, "atto").split("/")[-1]
            url_a   = val(r, "url_atto")[-50:]
            url_v   = val(r, "url_vta")[-50:]
            match   = "==" if url_a == url_v else "!="
            print(f"  {atto_id}: url_atto ...{url_a}  {match}  url_vta ...{url_v}")
    else:
        print("  (confronto non disponibile)")

    # Count: how many vta have dc:isReferencedBy instead of dc:relation?
    rows_iref = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dcterms: <{DCT}>
SELECT (COUNT(DISTINCT ?vta) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_versioneTestoAtto ?vta .
  ?vta dcterms:isReferencedBy ?url .
}}
""", "vta con dcterms:isReferencedBy", silent=True)
    n_iref = val(rows_iref[0], "n") if rows_iref else "?"
    print(f"\n  vta con dcterms:isReferencedBy: {n_iref}")

    time.sleep(1)


# ── P4. Formato ocd:primo_firmatario ──────────────────────────────────────

def p4_primo_firmatario(leg: int) -> None:
    """Check whether ocd:primo_firmatario holds URIs or string literals.

    If URIs: we can join with t_deputati (anagrafica Camera, future task).
    If literals: we get only the name string (less useful for analysis).
    """
    sep(4, f"Formato ocd:primo_firmatario (Leg{leg})")
    leg_u = leg_uri(leg)

    rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT DISTINCT ?val (DATATYPE(?val) AS ?dtype) (LANG(?val) AS ?lang)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:primo_firmatario ?val .
}}
LIMIT 10
""", "primo_firmatario sample", silent=True)

    if rows:
        print(f"  Valori ocd:primo_firmatario:")
        for r in rows:
            v     = val(r, "val")
            dtype = val(r, "dtype") or "(URI)" if v.startswith("http") else "(literal)"
            print(f"    {v[:70]}  [{dtype}]")
    else:
        print("  ⚠️ Nessun valore trovato.")

    # If URI: check what class/properties it has
    rows_u = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT DISTINCT ?pf
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:primo_firmatario ?pf .
  FILTER(isURI(?pf))
}}
LIMIT 3
""", "URI primo_firmatario", silent=True)

    if rows_u:
        print(f"\n  Dump proprietà di un primo_firmatario URI:")
        pf_uri = val(rows_u[0], "pf")
        props  = sparql(f"SELECT ?p ?o WHERE {{ <{pf_uri}> ?p ?o }}",
                        "props pf", silent=True)
        print(f"  URI: {pf_uri}")
        for r in props:
            p = short(val(r, "p"))
            o = val(r, "o")
            print(f"    {p:<35}  {o[:75]}")
    else:
        print("\n  (nessun URI trovato — primo_firmatario è un letterale)")

    time.sleep(1)


# ── P5. ocd:rif_natura — label testuale ───────────────────────────────────

def p5_natura(leg: int) -> None:
    """Get label text of ocd:rif_natura values.

    From diag_camera_atti.py: ocd:rif_natura URI last segment is
    'proposta_legge_ordinaria'. We want the human-readable label.
    """
    sep(5, f"ocd:rif_natura — distribuzione e label (Leg{leg})")
    leg_u = leg_uri(leg)

    rows = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX rdfs: <{RDFS}>
SELECT ?natura ?label (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_natura ?natura .
  OPTIONAL {{ ?natura rdfs:label ?label }}
}}
GROUP BY ?natura ?label
ORDER BY DESC(?n)
""", f"natura Leg{leg}", silent=True)

    if rows:
        print(f"  {'N atti':>8}  {'URI natura':45}  Label")
        print("-" * 80)
        for r in rows:
            n    = val(r, "n")
            nat  = val(r, "natura").split("/")[-1]
            lbl  = val(r, "label") or "(no label)"
            print(f"  {n:>8}  {nat:<45}  {lbl[:30]}")
    else:
        print("  ⚠️ Nessun risultato.")

    # Try dc:title on natura
    rows_t = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?v
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_natura ?nat .
  ?nat dc:title ?v .
}}
LIMIT 5
""", "natura dc:title", silent=True)
    if rows_t:
        print(f"  dc:title su natura: {[val(r,'v') for r in rows_t]}")

    time.sleep(1)


# ── P6. Distribuzione dc:relation e identificazione PDF testo presentato ──

def p6_url_pattern(leg: int) -> None:
    """Analyze URL patterns in dc:relation to identify the presented text PDF.

    From the sample dump:
      dc:relation = http://www.camera.it/_dati/leg17/lavori/stampati/pdf/17PDL0000010.pdf
    Pattern: /_dati/leg{N}/lavori/stampati/pdf/{code}.pdf

    Goal: confirm this pattern is consistent across all atti and all legislatures,
    so we can use it as the canonical 'testo presentato' URL.
    """
    sep(6, f"Pattern URL dc:relation — identificazione PDF testo presentato (Leg{leg})")
    leg_u = leg_uri(leg)

    # Fetch 15 dc:relation values to see URL patterns
    rows = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?atto ?url
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        dc:relation ?url .
}}
LIMIT 20
""", f"campione URL Leg{leg}", silent=True)

    patterns: dict[str, int] = {}
    if rows:
        print(f"  Campione URL dc:relation (Leg{leg}):")
        for r in rows:
            u = val(r, "url")
            # Classify by path pattern
            if "/_dati/" in u and "/stampati/pdf/" in u:
                pat = "/_dati/legN/lavori/stampati/pdf/*.pdf"
            elif "/_dati/" in u and "/lavori/" in u:
                pat = "/_dati/legN/lavori/...  (non-PDF)"
            elif "camera.it" in u and ".pdf" in u.lower():
                pat = "camera.it/*.pdf (altro)"
            elif "camera.it" in u:
                pat = "camera.it/* (non-PDF)"
            else:
                pat = "altra origine"
            patterns[pat] = patterns.get(pat, 0) + 1
            ext = u.rsplit(".", 1)[-1].lower()[:4] if "." in u else "?"
            atto_id = val(r, "atto").split("/")[-1]
            print(f"    [{ext}] {u[:85]}")

    print(f"\n  Classificazione pattern ({len(rows)} URL campione):")
    for pat, cnt in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"    {cnt:>4}  {pat}")

    # Verify URL pattern on another legislature (leg 18)
    if leg != 18:
        leg_u18 = leg_uri(18)
        rows18 = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?url
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u18}> ;
        dc:relation ?url .
}}
LIMIT 5
""", "campione URL Leg18", silent=True)
        if rows18:
            print(f"\n  Campione URL Leg18 (cross-check pattern):")
            for r in rows18:
                print(f"    {val(r,'url')[:85]}")

    time.sleep(1)


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Esplora struttura ocd:statoIter e dc:relation nel triplestore Camera."
    )
    parser.add_argument("--leg",     type=int, default=17,
                        help="Legislatura campione (default: 17)")
    parser.add_argument("--section", type=int, default=0,
                        help="Esegui solo questa sezione P# (0=tutte, default: 0)")
    args = parser.parse_args()

    print("=" * 72)
    print("diag_camera_stato_testo.py — Struttura statoIter e dc:relation")
    print(f"Endpoint: {EP}")
    print(f"Legislatura campione: Leg{args.leg}")
    print("=" * 72)

    run = args.section

    if run in (0, 1):  p1_stato_iter(args.leg)
    if run in (0, 2):  p2_dc_relation(args.leg)
    if run in (0, 3):  p3_versione_testo(args.leg)
    if run in (0, 4):  p4_primo_firmatario(args.leg)
    if run in (0, 5):  p5_natura(args.leg)
    if run in (0, 6):  p6_url_pattern(args.leg)

    print(f"\n{'=' * 72}")
    print("Diagnostica completata.")
    print()
    print("INTERPRETAZIONE ATTESA:")
    print("  P1: ocd:statoIter dovrebbe avere dc:title o rdfs:label con il testo")
    print("      (es. 'Approvato', 'Ritirato', 'In iter') e una proprietà data.")
    print("      Se non ha data → useremo MAX(URI) come proxy dell'ultimo stato.")
    print("  P2: se tutti gli URL hanno pattern /_dati/legN/lavori/stampati/pdf/")
    print("      → URL testo presentato è estraibile direttamente da dc:relation.")
    print("      Se ci sono URL multipli per atto → filtrare per .pdf nel path.")
    print("  P3: se vta ha le stesse URL → dc:relation su atto è ridondante con vta;")
    print("      usare dc:relation sull'atto direttamente (più semplice).")
    print("  P4: se primo_firmatario è URI → join futuro con t_deputati possibile.")
    print("  P5: natura con rdfs:label → colonna leggibile nel parquet.")
    print("  P6: pattern URL confermato → regex per filtrare il PDF principale.")


if __name__ == "__main__":
    main()
