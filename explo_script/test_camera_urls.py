#!/usr/bin/env python3
"""
test_camera_urls.py — Recupera e testa gli URL COMPLETI dei documenti Camera.

Tre tipi di URL da verificare:
  1. isReferencedBy su ocd:versioneTestoAtto  (testi presentati / versioni atto)
  2. relation su ocd:allegatoDiscussione       (allegati: emendamenti, pareri...)
  3. isReferencedBy su ocd:atto               (scheda atto principale)

Per ognuno: stampa l'URL intero, testa HEAD e GET, classifica la risposta.

Usage:
  python3 script_prova/test_camera_urls.py
  python3 script_prova/test_camera_urls.py --legs 17 19
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request

CAMERA_SPARQL = "https://dati.camera.it/sparql"
ALL_LEGS      = [13, 14, 15, 16, 17, 18, 19]
OCD           = "http://dati.camera.it/ocd/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/xml,text/xml,text/html,*/*;q=0.8",
}


def leg_uri(n: int) -> str:
    return f"{OCD}legislatura.rdf/repubblica_{n}"


# ---------------------------------------------------------------------------
# SPARQL
# ---------------------------------------------------------------------------

def cam(query: str, label: str = "", timeout: int = 30) -> list[dict]:
    params = urllib.parse.urlencode({
        "query":  query,
        "format": "application/sparql-results+json",
    })
    req = urllib.request.Request(
        f"{CAMERA_SPARQL}?{params}",
        headers={"Accept": "application/sparql-results+json",
                 "User-Agent": "iter-legis-explorer/1.0"},
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


# ---------------------------------------------------------------------------
# HTTP test
# ---------------------------------------------------------------------------

def test_url(url: str) -> tuple[int, str, str]:
    """
    Testa un URL con GET.
    Ritorna (status, content_type, classificazione).
    """
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            ct   = r.headers.get("Content-Type", "")
            body = r.read(800).decode("utf-8", errors="replace")
            st   = r.status

            ct_low = ct.lower()
            if "pdf" in ct_low:
                return st, ct, "PDF ✅"
            if "xml" in ct_low or body.strip().startswith("<?xml"):
                if "akomantoso" in body.lower():
                    return st, ct, "AKN ✅"
                return st, ct, "XML"
            if "<html" in body.lower():
                import re
                m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                title = m.group(1).strip()[:60] if m else ""
                if any(w in title.lower() for w in ["errore", "not found", "404"]):
                    return st, ct, f"HTML errore ({title})"
                return st, ct, f"HTML ({title})"
            if body.strip().startswith("%PDF"):
                return st, ct, "PDF ✅ (no CT)"
            return st, ct, f"altro ({body[:40]!r})"

    except urllib.error.HTTPError as e:
        return e.code, "", f"HTTP {e.code}"
    except Exception as e:
        return -1, "", str(e)


def report(label: str, url: str) -> None:
    print(f"\n  [{label}]")
    print(f"  URL: {url}")
    st, ct, cls = test_url(url)
    sym = "✅" if st == 200 and ("✅" in cls) else ("⚠️ " if st == 200 else "✗ ")
    print(f"  {sym} HTTP {st}  |  {cls}")
    if ct:
        print(f"  CT: {ct}")


# ---------------------------------------------------------------------------
# Sezione 1 — isReferencedBy su versioneTestoAtto
# ---------------------------------------------------------------------------

def sezione_vta(legs: list[int]) -> None:
    print("\n" + "=" * 70)
    print("1 — URL COMPLETI: isReferencedBy su ocd:versioneTestoAtto")
    print("=" * 70)

    for leg in legs:
        leg_u = leg_uri(leg)
        print(f"\n  --- Leg{leg} ---")

        q = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?vta ?url ?titolo
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ocd:rif_versioneTestoAtto ?vta .
  ?vta <http://purl.org/dc/elements/1.1/isReferencedBy> ?url .
  OPTIONAL {{ ?vta <http://purl.org/dc/terms/title> ?titolo }}
  OPTIONAL {{ ?vta <http://purl.org/dc/elements/1.1/title> ?titolo }}
}}
LIMIT 3
"""
        rows = cam(q, f"Leg{leg} vta + isReferencedBy")

        if not rows:
            q2 = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?vta ?url ?titolo
WHERE {
  ?vta a ocd:versioneTestoAtto ;
       <http://purl.org/dc/elements/1.1/isReferencedBy> ?url .
  OPTIONAL { ?vta <http://purl.org/dc/elements/1.1/title> ?titolo }
}
LIMIT 3
"""
            rows = cam(q2, f"Leg{leg} vta globale (fallback)")

        if not rows:
            print(f"  ⚠️  Nessun versioneTestoAtto con isReferencedBy per Leg{leg}")
            continue

        for r in rows:
            vta    = v(r, "vta").split("/")[-1]
            url    = v(r, "url")
            titolo = v(r, "titolo") or "(nessun titolo)"
            print(f"\n  vta={vta}")
            print(f"  Titolo: {titolo[:80]}")
            report("isReferencedBy", url)
            time.sleep(0.3)

        time.sleep(0.5)


# ---------------------------------------------------------------------------
# Sezione 2 — relation su allegatoDiscussione (emendamenti)
# ---------------------------------------------------------------------------

def sezione_allegati(legs: list[int]) -> None:
    print("\n" + "=" * 70)
    print("2 — URL COMPLETI: relation su ocd:allegatoDiscussione (emendamenti)")
    print("=" * 70)

    emend_labels = [
        "Emendamenti",
        "Proposte emendative presentate",
        "Proposte emendative approvate",
        "Nuovo testo",
    ]

    for leg in legs:
        leg_u = leg_uri(leg)
        print(f"\n  --- Leg{leg} ---")
        found = False

        for kw in emend_labels:
            q = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?all ?url ?label
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ocd:rif_leg <{leg_u}> ;
       <http://purl.org/dc/elements/1.1/relation> ?url .
  OPTIONAL {{ ?all <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
  FILTER(CONTAINS(?label, "{kw}"))
}}
LIMIT 2
"""
            rows = cam(q, f"Leg{leg} allegato '{kw}'")
            if rows:
                found = True
                for r in rows:
                    all_id = v(r, "all").split("/")[-1]
                    url    = v(r, "url")
                    label  = v(r, "label") or kw
                    print(f"\n  allegato={all_id}  label={label[:60]}")
                    report(f"relation ({kw})", url)
                    time.sleep(0.3)

        if not found:
            q_any = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?all ?url ?label
WHERE {{
  ?all a ocd:allegatoDiscussione ;
       ocd:rif_leg <{leg_u}> ;
       <http://purl.org/dc/elements/1.1/relation> ?url .
  OPTIONAL {{ ?all <http://www.w3.org/2000/01/rdf-schema#label> ?label }}
}}
LIMIT 2
"""
            rows2 = cam(q_any, f"Leg{leg} allegato qualsiasi")
            if rows2:
                for r in rows2:
                    all_id = v(r, "all").split("/")[-1]
                    url    = v(r, "url")
                    label  = v(r, "label") or "(nessuna label)"
                    print(f"\n  allegato={all_id}  label={label[:60]}")
                    report("relation (qualsiasi)", url)
                    time.sleep(0.3)
            else:
                print(f"  ⚠️  Nessun allegatoDiscussione con URL per Leg{leg}")

        time.sleep(0.5)


# ---------------------------------------------------------------------------
# Sezione 3 — Leg16: indaga l'anomalia PDF
# ---------------------------------------------------------------------------

def sezione_leg16() -> None:
    print("\n" + "=" * 70)
    print("3 — Leg16 anomalia: cerca URL testo con predicati alternativi")
    print("=" * 70)

    leg_u = leg_uri(16)

    q = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?p (COUNT(?atto) AS ?n) (SAMPLE(?val) AS ?esempio)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        ?p ?val .
  FILTER(
    CONTAINS(STR(?val), "http") &&
    (
      CONTAINS(STR(?val), ".pdf")  ||
      CONTAINS(STR(?val), ".xml")  ||
      CONTAINS(STR(?val), ".akn")  ||
      CONTAINS(STR(?val), "camera.it") ||
      CONTAINS(STR(?val), "stampat")
    )
  )
}}
GROUP BY ?p
ORDER BY DESC(?n)
LIMIT 20
"""
    rows = cam(q, "Leg16 predicati con URL camera.it", timeout=60)
    print(f"\n  Predicati con URL camera.it su atti Leg16:")
    for r in rows:
        p   = v(r, "p").split("/")[-1].split("#")[-1]
        n   = v(r, "n")
        ex  = v(r, "esempio")
        print(f"    {p:<35}  n={n:>6}  es: {ex[:60]}")

    time.sleep(0.5)

    q2 = f"""
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
LIMIT 1
"""
    rows2 = cam(q2, "atto campione Leg16")
    if rows2:
        atto_uri = v(rows2[0], "atto")
        print(f"\n  Tutte le proprietà di {atto_uri.split('/')[-1]} (Leg16):")
        q3 = f"SELECT ?p ?o WHERE {{ <{atto_uri}> ?p ?o . }}"
        props = cam(q3, "props atto Leg16")
        for r in props:
            p = v(r, "p").split("/")[-1].split("#")[-1]
            o = v(r, "o")
            flag = "  ◀ URL" if "http" in o and len(o) > 20 else ""
            print(f"    {p:<35}  {o[:70]}{flag}")


# ---------------------------------------------------------------------------
# Sezione 4 — ocd:rif_attoSenato: campione di link Camera→Senato
# ---------------------------------------------------------------------------

def sezione_rif_senato() -> None:
    print("\n" + "=" * 70)
    print("4 — ocd:rif_attoSenato: campione link Camera → Senato")
    print("=" * 70)

    q = """
PREFIX ocd: <http://dati.camera.it/ocd/>
SELECT ?tr ?rif_sen ?label
WHERE {
  ?tr a ocd:trasmissione ;
      ocd:rif_attoSenato ?rif_sen .
  OPTIONAL { ?tr <http://www.w3.org/2000/01/rdf-schema#label> ?label }
}
LIMIT 10
"""
    rows = cam(q, "campione rif_attoSenato")
    print(f"\n  {'Trasmissione':<30}  {'rif_attoSenato':<55}  Label")
    print("  " + "-" * 120)
    for r in rows:
        tr  = v(r, "tr").split("/")[-1]
        rs  = v(r, "rif_sen")
        lab = v(r, "label")[:50] if v(r, "label") else ""
        print(f"  {tr:<30}  {rs:<55}  {lab}")

    time.sleep(0.5)

    if rows:
        first_rs = v(rows[0], "rif_sen")
        print(f"\n  Primo rif_attoSenato: {first_rs}")
        if first_rs.startswith("http://dati.senato.it"):
            print("  → URI del triplestore Senato: collegamento diretto via SPARQL!")
        else:
            print(f"  → Formato sconosciuto: {first_rs[:80]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Testa URL completi di versioneTestoAtto e allegatoDiscussione."
    )
    parser.add_argument(
        "--legs", type=int, nargs="+", default=ALL_LEGS,
        help=f"Legislature (default: {ALL_LEGS})"
    )
    args = parser.parse_args()

    print("test_camera_urls.py — URL completi documenti Camera dei Deputati")
    print(f"Endpoint: {CAMERA_SPARQL}")
    print(f"Legislature: {args.legs}")

    sezione_vta(args.legs)
    time.sleep(1)
    sezione_allegati(args.legs)
    time.sleep(1)
    sezione_leg16()
    time.sleep(1)
    sezione_rif_senato()

    print(f"\n{'='*70}")
    print("✅ Test completato.")


if __name__ == "__main__":
    main()
