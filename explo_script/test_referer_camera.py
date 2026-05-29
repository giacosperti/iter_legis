#!/usr/bin/env python3
"""
test_referer_camera.py — Testa se aggiungere Referer e cookie di sessione
                         sblocca il "Request Rejected" su getDocumento.ashx.

Prova in sequenza header sempre più completi sullo stesso URL di emendamento.

Usage:
  python3 script_prova/test_referer_camera.py
"""

import urllib.request
import urllib.error
import http.cookiejar

# URL emendamento noto (Leg17, da sezione 2 dello script precedente)
TEST_URL = (
    "http://documenti.camera.it/apps/commonServices/getDocumento.ashx"
    "?sezione=bollettini&tipoDoc=allegato&idLegislatura=17"
    "&anno=2014&mese=05&giorno=14&idcommissione=0108"
    "&pagina=data.20140514.com0108.allegati.all00010"
    "&ancora=data.20140514.com0108.allegati.all00010"
)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


def try_request(label: str, extra_headers: dict) -> None:
    headers = {**BASE_HEADERS, **extra_headers}
    req = urllib.request.Request(TEST_URL, headers=headers)
    print(f"\n  [{label}]")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            ct   = r.headers.get("Content-Type", "(nessuno)")
            body = r.read(6000).decode("utf-8", errors="replace")
            print(f"  HTTP {r.status}  CT: {ct[:60]}")
            if "pdf" in ct.lower() or body[:4] == "%PDF":
                print(f"  → PDF ✅")
            elif "Request Rejected" in body:
                print(f"  → Request Rejected ❌")
            elif any(kw in body.lower() for kw in
                     ["emendament", "proposta", "articolo", "comma",
                      "disegno di legge", "testo", "approvato"]):
                import re
                title = ""
                m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                if m:
                    title = m.group(1).strip()[:80]
                testo = re.sub(r"<[^>]+>", " ", body)
                testo = " ".join(testo.split())[:400]
                print(f"  → CONTENUTO REALE ✅")
                if title:
                    print(f"  Titolo: {title}")
                print(f"  Testo estratto: {testo[:400]}")
            else:
                import re
                m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                title = m.group(1).strip()[:80] if m else ""
                print(f"  → HTML  title={title!r}")
                print(f"  body[200:500]: {body[200:500]!r}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"  Errore: {e}")


def try_with_session() -> None:
    """
    Simula un browser reale:
    1. Visita prima la homepage di documenti.camera.it (ottiene cookie di sessione)
    2. Poi richiede l'URL dell'allegato usando quei cookie + Referer
    """
    print("\n  [Con sessione reale: visita homepage → poi allegato]")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    home_url = "http://documenti.camera.it/"
    home_req = urllib.request.Request(home_url, headers={
        **BASE_HEADERS,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    })
    try:
        with opener.open(home_req, timeout=15) as r:
            cookies_received = list(jar)
            print(f"  Homepage: HTTP {r.status}  Cookie ricevuti: {len(cookies_received)}")
            for c in cookies_received:
                print(f"    {c.name}={c.value[:30]}...")
    except Exception as e:
        print(f"  Errore homepage: {e}")

    doc_req = urllib.request.Request(TEST_URL, headers={
        **BASE_HEADERS,
        "Referer": "http://documenti.camera.it/",
        "Accept": "application/pdf,text/html,*/*;q=0.8",
    })
    try:
        with opener.open(doc_req, timeout=15) as r:
            ct   = r.headers.get("Content-Type", "(nessuno)")
            body = r.read(6000).decode("utf-8", errors="replace")
            print(f"  Allegato: HTTP {r.status}  CT: {ct[:60]}")
            if "pdf" in ct.lower():
                print(f"  → PDF ✅")
            elif "Request Rejected" in body:
                print(f"  → Request Rejected ❌")
            elif any(kw in body.lower() for kw in
                     ["emendament", "proposta", "articolo", "comma"]):
                import re
                testo = re.sub(r"<[^>]+>", " ", body)
                testo = " ".join(testo.split())[:400]
                print(f"  → CONTENUTO REALE ✅")
                print(f"  Testo: {testo[:400]}")
            else:
                print(f"  → body[200:500]: {body[200:500]!r}")
    except Exception as e:
        print(f"  Errore allegato: {e}")


def main() -> None:
    print("test_referer_camera.py — Test header per sbloccare getDocumento.ashx")
    print(f"URL: {TEST_URL[:80]}...")
    print("=" * 70)

    try_request("Solo User-Agent", {})

    try_request("+ Referer documenti.camera.it", {
        "Referer": "http://documenti.camera.it/",
    })

    try_request("+ Referer bollettino commissioni", {
        "Referer": (
            "http://documenti.camera.it/leg/17/resoconti/"
            "commissioni/bollettini/pdf/2014/05/14/leg.17.bol0514.data20140514.com0108.pdf"
        ),
    })

    try_request("+ Referer + Accept PDF", {
        "Referer": "http://documenti.camera.it/",
        "Accept": "application/pdf,*/*;q=0.8",
    })

    try_request("+ Referer + Connection keep-alive", {
        "Referer": "http://documenti.camera.it/",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    })

    try_with_session()

    print(f"\n{'='*70}")
    print("✅ Test completato.")


if __name__ == "__main__":
    main()
