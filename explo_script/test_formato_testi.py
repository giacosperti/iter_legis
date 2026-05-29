#!/usr/bin/env python3
"""
test_formato_testi.py — Verifica se i testi presentati sono disponibili
                        in formati migliori del PDF (HTML, AKN/XML).

Testa per Camera e Senato:
  1. Camera: versioneTestoAtto.isReferencedBy con Referer (HTML come emendamenti?)
  2. Camera: URL stampati con varianti formato (?formato=xml, .xml, ecc.)
  3. Camera: URI resolver (uri-res/N2Ls) per atti Camera
  4. Senato Leg17-19: GitHub ddlpres AKN (già noto ✅, solo conferma)
  5. Senato Leg13-16: NIR URN via normattiva + altre varianti

Usage:
  python3 script_prova/test_formato_testi.py
"""

from __future__ import annotations
import json
import time
import urllib.error
import urllib.parse
import urllib.request

CAMERA_SPARQL = "https://dati.camera.it/sparql"
OCD           = "http://dati.camera.it/ocd/"

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9",
}
HEADERS_WITH_REFERER = {
    **HEADERS_BASE,
    "Referer": "http://documenti.camera.it/",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def sparql_cam(query: str, label: str = "", timeout: int = 30) -> list[dict]:
    params = urllib.parse.urlencode({
        "query": query, "format": "application/sparql-results+json"
    })
    req = urllib.request.Request(
        f"{CAMERA_SPARQL}?{params}",
        headers={"Accept": "application/sparql-results+json",
                 "User-Agent": "iter-legis-explorer/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            rows = data.get("results", {}).get("bindings", [])
            if label:
                print(f"    [{label}] → {len(rows)} righe")
            return rows
    except Exception as e:
        print(f"    [{label}] errore: {e}")
        return []

def v(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "")

def classify(status: int, ct: str, body: str) -> str:
    if status not in (200, 206):
        return f"errore HTTP {status}"
    ct_low = ct.lower()
    body_low = body.lower()
    if "pdf" in ct_low or body[:4] == "%PDF":
        return "PDF ✅"
    if "xml" in ct_low or body.lstrip("﻿").startswith("<?xml"):
        if "akomantoso" in body_low:
            return "AKN ✅"
        return "XML"
    if "<html" in body_low or "<!doctype" in body_low:
        import re
        m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        title = m.group(1).strip()[:60] if m else ""
        has_content = any(kw in body_low for kw in
            ["emendament", "proposta", "articolo", "comma",
             "disegno di legge", "legislatur", "testo"])
        if has_content:
            return f"HTML con contenuto ✅ (title: {title})"
        return f"HTML vuoto/errore (title: {title})"
    return f"sconosciuto ({body[:40]!r})"

def fetch(url: str, headers: dict = HEADERS_BASE, timeout: int = 15) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct   = r.headers.get("Content-Type", "")
            body = r.read(3000).decode("utf-8", errors="replace")
            return r.status, ct, body
    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:
        return -1, "", str(e)

def test_url(label: str, url: str, headers: dict = HEADERS_BASE) -> str:
    status, ct, body = fetch(url, headers)
    result = classify(status, ct, body)
    sym = "✅" if "✅" in result else ("⚠️ " if status == 200 else "✗ ")
    print(f"  {sym} [{label}]  HTTP {status}  →  {result}")
    print(f"     URL: {url[:100]}")
    if "HTML con contenuto" in result:
        import re
        testo = re.sub(r"<[^>]+>", " ", body)
        testo = " ".join(testo.split())[:300]
        print(f"     Testo: {testo[:300]}")
    return result


# ---------------------------------------------------------------------------
# 1 — Camera: versioneTestoAtto.isReferencedBy con Referer
# ---------------------------------------------------------------------------

def sezione_1_camera_vta() -> None:
    print("\n" + "=" * 70)
    print("1 — Camera: versioneTestoAtto con Referer (come emendamenti?)")
    print("=" * 70)

    q = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?vta ?url ?titolo
WHERE {
  ?vta a ocd:versioneTestoAtto ;
       ?p ?url .
  FILTER(CONTAINS(LCASE(STR(?p)), "referenced") || CONTAINS(LCASE(STR(?p)), "source"))
  FILTER(CONTAINS(STR(?url), "http"))
  OPTIONAL { ?vta ?pt ?titolo . FILTER(CONTAINS(LCASE(STR(?pt)), "title")) }
}
LIMIT 5
"""
    rows = sparql_cam(q, "vta isReferencedBy URL")

    if not rows:
        q2 = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?vta ?p ?url
WHERE {
  ?vta a ocd:versioneTestoAtto ;
       ?p ?url .
  FILTER(CONTAINS(STR(?url), "documenti.camera.it") ||
         CONTAINS(STR(?url), "camera.it/_dati"))
}
LIMIT 5
"""
        rows = sparql_cam(q2, "vta URL camera.it (generico)")

    if not rows:
        print("  ⚠️  Nessun URL trovato su versioneTestoAtto — "
              "forse usa namespace diverso per isReferencedBy")
        q3 = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?vta ?p ?o
WHERE {
  ?vta a ocd:versioneTestoAtto ;
       ?p ?o .
  FILTER(CONTAINS(STR(?o), "http"))
}
LIMIT 10
"""
        rows3 = sparql_cam(q3, "vta con qualsiasi URL")
        for r in rows3:
            print(f"    vta={v(r,'vta').split('/')[-1]}  {v(r,'p').split('/')[-1]}  {v(r,'o')}")
        return

    for r in rows:
        url = v(r, "url") or v(r, "o")
        tit = v(r, "titolo") or ""
        if not url or not url.startswith("http"):
            continue
        print(f"\n  Titolo: {tit[:70]}")
        test_url("senza Referer", url, HEADERS_BASE)
        test_url("con Referer", url, HEADERS_WITH_REFERER)
        time.sleep(0.3)


# ---------------------------------------------------------------------------
# 2 — Camera: stampati PDF → varianti formato
# ---------------------------------------------------------------------------

def sezione_2_camera_formati() -> None:
    print("\n" + "=" * 70)
    print("2 — Camera: stampati PDF con varianti formato (XML, HTML, AKN)")
    print("=" * 70)

    q = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?atto ?pdf_url
WHERE {
  ?atto a ocd:atto ;
        ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_17> ;
        <http://purl.org/dc/elements/1.1/relation> ?pdf_url .
  FILTER(CONTAINS(STR(?pdf_url), ".pdf"))
}
LIMIT 1
"""
    rows = sparql_cam(q, "atto Leg17 con PDF")
    if not rows:
        print("  ⚠️  Nessun atto trovato")
        return

    pdf_url = v(rows[0], "pdf_url")
    base    = pdf_url.replace(".pdf", "")
    print(f"\n  URL base: {base}")

    varianti = [
        ("PDF originale",    pdf_url),
        ("→ .xml",           base + ".xml"),
        ("→ .htm",           base + ".htm"),
        ("→ .html",          base + ".html"),
        ("→ .akn",           base + ".akn"),
        ("→ .rtf",           base + ".rtf"),
        ("→ _testo.htm",     base + "_testo.htm"),
    ]
    for label, url in varianti:
        test_url(label, url)
        time.sleep(0.2)

    print(f"\n  PDF con Referer (per confronto):")
    test_url("PDF + Referer", pdf_url, HEADERS_WITH_REFERER)

    q2 = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?atto ?ref
WHERE {
  ?atto a ocd:atto ;
        ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_17> ;
        <http://purl.org/dc/elements/1.1/isReferencedBy> ?ref .
  FILTER(CONTAINS(STR(?ref), "camera.it"))
}
LIMIT 3
"""
    rows2 = sparql_cam(q2, "atto Leg17 isReferencedBy")
    if rows2:
        print(f"\n  URI resolver Camera (isReferencedBy su ocd:atto):")
        for r in rows2:
            url = v(r, "ref")
            test_url("uri-res N2Ls", url)
            test_url("uri-res N2Ls + Referer", url, HEADERS_WITH_REFERER)
            time.sleep(0.2)


# ---------------------------------------------------------------------------
# 3 — Camera: URI resolver e varianti formato per Leg13
# ---------------------------------------------------------------------------

def sezione_3_camera_leg13() -> None:
    print("\n" + "=" * 70)
    print("3 — Camera Leg13: formati disponibili per testo presentato")
    print("=" * 70)

    q = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?atto ?pdf_url
WHERE {
  ?atto a ocd:atto ;
        ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_13> ;
        <http://purl.org/dc/elements/1.1/relation> ?pdf_url .
  FILTER(CONTAINS(STR(?pdf_url), ".pdf"))
}
LIMIT 2
"""
    rows = sparql_cam(q, "atto Leg13 con PDF")
    for r in rows:
        pdf_url = v(r, "pdf_url")
        base    = pdf_url.replace(".pdf", "")
        print(f"\n  URL: {pdf_url}")
        varianti = [
            ("PDF",    pdf_url),
            ("→ .xml", base + ".xml"),
            ("→ .htm", base + ".htm"),
            ("→ .akn", base + ".akn"),
        ]
        for label, url in varianti:
            test_url(label, url)
            time.sleep(0.2)


# ---------------------------------------------------------------------------
# 4 — Senato Leg13-16: NIR URN → formati alternativi
# ---------------------------------------------------------------------------

def sezione_4_senato_leg13_16() -> None:
    print("\n" + "=" * 70)
    print("4 — Senato Leg13-16: testo presentato via NIR URN e varianti")
    print("=" * 70)

    campioni = [
        (13, "urn:nir:senato.repubblica:disegno.legge:13.legislatura;4787"),
        (16, "urn:nir:senato.repubblica:disegno.legge:16.legislatura;1092"),
    ]

    for leg, urn in campioni:
        print(f"\n  Leg{leg} — URN: {urn}")

        varianti = [
            ("normattiva N2Ls",
             f"https://www.normattiva.it/uri-res/N2Ls?{urn}"),
            ("normattiva N2Ls AKN",
             f"https://www.normattiva.it/uri-res/N2Ls?{urn}!vig="),
            ("senato URI-res",
             f"https://www.senato.it/uri-res/N2Ls?{urn}"),
            ("BGT Senato + Referer",
             f"https://www.senato.it/leg/{leg}/BGT/Testi/Ddlpres/"
             f"{int(urn.split(';')[-1]):08d}.akn"),
        ]
        bgt_url_with_referer_headers = {
            **HEADERS_BASE,
            "Referer": f"https://www.senato.it/legislature/{leg}/"
                       f"leggi-e-documenti/disegni-di-legge/",
        }

        for i, (label, url) in enumerate(varianti):
            hdrs = bgt_url_with_referer_headers if "BGT Senato" in label else HEADERS_BASE
            test_url(label, url, hdrs)
            time.sleep(0.3)


# ---------------------------------------------------------------------------
# 5 — Senato Leg17-19: conferma AKN GitHub ddlpres
# ---------------------------------------------------------------------------

def sezione_5_senato_leg17_19() -> None:
    print("\n" + "=" * 70)
    print("5 — Senato Leg17-19: ddlpres AKN via GitHub (conferma)")
    print("=" * 70)

    q = """
PREFIX osr: <http://dati.senato.it/osr/>
SELECT ?ddl ?urn ?num
WHERE {
  ?ddl a osr:Ddl ;
       osr:legislatura 19 ;
       osr:progressivoIter 1 ;
       osr:testoPresentato ?urn ;
       osr:numero ?num .
}
LIMIT 2
"""
    import urllib.request as ur
    params = urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"})
    try:
        with ur.urlopen(
            ur.Request(f"https://dati.senato.it/sparql?{params}",
                       headers={"Accept": "application/sparql-results+json",
                                "User-Agent": "iter-legis-explorer/1.0"}),
            timeout=30
        ) as resp:
            data = json.loads(resp.read().decode())
            rows = data.get("results", {}).get("bindings", [])
            print(f"    [ddl Leg19 testoPresentato] → {len(rows)} righe")
    except Exception as e:
        print(f"    errore SPARQL Senato: {e}")
        rows = []

    for r in rows:
        num = v(r, "num")
        urn = v(r, "urn")
        print(f"\n  S.{num}  URN: {urn}")
        num_pad = f"{int(num):04d}"
        gh_url = (f"https://raw.githubusercontent.com/senato-it/"
                  f"AkomaNtosoBulkData/main/DDL/Leg19/Ddlpres/S{num_pad}.akn")
        test_url("GitHub ddlpres AKN", gh_url)
        time.sleep(0.2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("test_formato_testi.py — Verifica formati per testo presentato")
    print("=" * 70)

    sezione_1_camera_vta()
    time.sleep(0.5)
    sezione_2_camera_formati()
    time.sleep(0.5)
    sezione_3_camera_leg13()
    time.sleep(0.5)
    sezione_4_senato_leg13_16()
    time.sleep(0.5)
    sezione_5_senato_leg17_19()

    print(f"\n{'='*70}")
    print("✅ Test completato.")

if __name__ == "__main__":
    main()
