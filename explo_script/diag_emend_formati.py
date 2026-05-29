#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
diag_emend_formati.py — Esplora la disponibilità dei testi degli emendamenti
per tutte le legislature (Leg13–19) in tutti i formati disponibili.

Per ogni legislatura verifica:
  1. Quanti emendamenti totali esistono nel triplestore
  2. Quanti hanno osr:URLTestoXml  (formato AKN)
  3. Quanti hanno osr:URLTesto     (formato generico — HTML/PDF)
  4. Quanti hanno entrambi / solo uno / nessuno
  5. Campione di URL per capire il formato effettivo (estensione, dominio)

Obiettivo: capire se gli emendamenti non-AKN (specialmente Leg13/14)
sono disponibili in altri formati utilizzabili per l'analisi testuale.

Usage:
  uv run explo_script/diag_emend_formati.py
"""

import json
import time
import urllib.parse
import urllib.request

EP = "https://dati.senato.it/sparql"
H  = {"Accept": "application/sparql-results+json", "User-Agent": "iter-legis-diag/1.0"}


def sparql(query: str, label: str = "", timeout: int = 60) -> list[dict]:
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


print("=" * 70)
print("Disponibilità testi emendamenti per formato — Leg13–19")
print("=" * 70)

results = []

for leg in range(13, 20):
    print(f"\n── Leg{leg} ─────────────────────────────────────────────────")

    # 1. Totale emendamenti
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?emend) AS ?n)
WHERE {{ ?emend a osr:Emendamento ; osr:legislatura {leg} }}
""", "totale")
    n_tot = int(v(r[0], "n")) if r else 0

    # 2. Con URLTestoXml (AKN)
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?emend) AS ?n)
WHERE {{ ?emend a osr:Emendamento ; osr:legislatura {leg} ; osr:URLTestoXml ?url }}
""", "con AKN")
    n_akn = int(v(r[0], "n")) if r else 0

    # 3. Con URLTesto (formato generico)
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?emend) AS ?n)
WHERE {{ ?emend a osr:Emendamento ; osr:legislatura {leg} ; osr:URLTesto ?url }}
""", "con URLTesto")
    n_url = int(v(r[0], "n")) if r else 0

    # 4. Con entrambi
    r = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT (COUNT(DISTINCT ?emend) AS ?n)
WHERE {{
  ?emend a osr:Emendamento ; osr:legislatura {leg} ;
         osr:URLTestoXml ?akn ; osr:URLTesto ?url .
}}
""", "con entrambi")
    n_both = int(v(r[0], "n")) if r else 0

    # Derivati
    n_solo_akn = n_akn - n_both
    n_solo_url = n_url - n_both
    n_nessuno  = n_tot - n_akn - n_solo_url

    pct_akn = n_akn / n_tot * 100 if n_tot else 0
    pct_url = n_url / n_tot * 100 if n_tot else 0

    print(f"  Totale emendamenti  : {n_tot:>8,}")
    print(f"  Con AKN (XMLTesto)  : {n_akn:>8,}  ({pct_akn:.1f}%)")
    print(f"  Con URLTesto        : {n_url:>8,}  ({pct_url:.1f}%)")
    print(f"  Con entrambi        : {n_both:>8,}")
    print(f"  Solo AKN            : {n_solo_akn:>8,}")
    print(f"  Solo URLTesto       : {n_solo_url:>8,}")
    print(f"  Nessun testo        : {n_nessuno:>8,}")

    # 5. Campione URL per capire il formato
    r_sample = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?url
WHERE {{
  ?emend a osr:Emendamento ; osr:legislatura {leg} ; osr:URLTesto ?url .
}}
LIMIT 5
""", "campione URLTesto")

    if r_sample:
        print(f"\n  Campione URLTesto (fino a 5):")
        for row in r_sample:
            url = v(row, "url")
            # Estrai estensione e pattern
            ext = url.split(".")[-1].split("?")[0].lower() if "." in url else "?"
            print(f"    [{ext:>4}] {url[:90]}")

    # 6. Campione AKN per confronto
    r_akn_sample = sparql(f"""
PREFIX osr: <http://dati.senato.it/osr/>
SELECT DISTINCT ?url
WHERE {{
  ?emend a osr:Emendamento ; osr:legislatura {leg} ; osr:URLTestoXml ?url .
}}
LIMIT 3
""", "campione AKN")

    if r_akn_sample:
        print(f"\n  Campione URLTestoXml (AKN, fino a 3):")
        for row in r_akn_sample:
            url = v(row, "url")
            ext = url.split(".")[-1].split("?")[0].lower() if "." in url else "?"
            print(f"    [{ext:>4}] {url[:90]}")

    results.append({
        "leg": leg, "n_tot": n_tot, "n_akn": n_akn,
        "n_url": n_url, "n_both": n_both,
        "n_solo_akn": n_solo_akn, "n_solo_url": n_solo_url,
        "n_nessuno": n_nessuno,
        "pct_akn": round(pct_akn, 1), "pct_url": round(pct_url, 1),
    })

    time.sleep(1.5)

# ---------------------------------------------------------------------------
# Riepilogo finale
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("RIEPILOGO — Copertura testi emendamenti per formato")
print("=" * 70)
print(f"{'Leg':>4}  {'Totale':>8}  {'AKN':>8}  {'%AKN':>6}  "
      f"{'URLTesto':>9}  {'%URL':>6}  {'Entrambi':>9}  {'Nessuno':>8}")
print("-" * 70)
for r in results:
    print(f"  {r['leg']:>2}  {r['n_tot']:>8,}  {r['n_akn']:>8,}  {r['pct_akn']:>5.1f}%  "
          f"  {r['n_url']:>8,}  {r['pct_url']:>5.1f}%  {r['n_both']:>9,}  {r['n_nessuno']:>8,}")

print()
print("Legenda:")
print("  AKN      = osr:URLTestoXml — XML Akoma Ntoso (formato strutturato)")
print("  URLTesto = osr:URLTesto    — URL generico (HTML/PDF/altro)")
print("  Entrambi = emendamenti con entrambi i formati disponibili")
print("  Nessuno  = emendamenti senza alcun testo digitale accessibile")
print()
print("INTERPRETAZIONE:")
print("  - Se URLTesto >> AKN per Leg13/14 → esiste alternativa non-AKN")
print("  - Se URLTesto ≈ 0 per Leg13      → gli emendamenti non sono digitalizzati")
print("  - L'estensione degli URL di campione indica il formato effettivo")
print("    (es. .pdf, .htm, .html, .doc)")
