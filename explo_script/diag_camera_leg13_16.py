#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
diag_camera_leg13_16.py — Verifica copertura reale delle proprietà chiave
per Leg13–16 nel triplestore Camera dei Deputati.

Contesto:
  fetch_metadati_camera.py ha restituito 0% per natura/statoIter/testo su Leg13–15
  e 82.8% natura su Leg16. Questo script verifica se i 0% sono genuini (pre-digitale)
  o artefatti del fetch (bug keyset, batch VALUES troppo grandi, ecc.).

Domande:
  D1. Copertura raw (query diretta, no VALUES batch) di rif_natura, rif_statoIter,
      rif_versioneTestoAtto per Leg13–16. Stesso risultato del parquet?

  D2. Formato di dc:identifier per Leg13–16: ci sono valori non-interi
      ("105-B", "1061-bis", ecc.) come suggerito dal bug del keyset?
      Quanti atti avrebbero dc:identifier non-intero?

  D3. Dump completo di 3 atti campione per Leg13 e Leg14: hanno davvero 0 proprietà
      di contenuto, o sono strutturalmente diversi dagli atti Leg17?

  D4. Per Leg16: verifica diretta COUNT natura senza passare per batch VALUES.
      L'82.8% del parquet è confermato, o c'è di più nel triplestore?

  D5. rif_statoIter per Leg13–15: esistono istanze di statoIter collegate a
      atti di quelle legislature? E rif_versioneTestoAtto?

  D6. Tutte le proprietà di un atto Leg13 campione (dump completo).
      Confronto con schema atto Leg17 per vedere cosa manca.

Endpoint: https://dati.camera.it/sparql
Prefisso:  ocd: <http://dati.camera.it/ocd/>

Usage:
  python3 explo_script/diag_camera_leg13_16.py
  python3 explo_script/diag_camera_leg13_16.py --section 2
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

EP  = "https://dati.camera.it/sparql"
OCD = "http://dati.camera.it/ocd/"
DC  = "http://purl.org/dc/elements/1.1/"
DCT = "http://purl.org/dc/terms/"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"

LEGS_FOCUS = [13, 14, 15, 16]
LEGS_ALL   = [13, 14, 15, 16, 17, 18, 19]

HEADERS = {
    "Accept":     "application/sparql-results+json",
    "User-Agent": "iter-legis-diag/1.0 (leg13_16)",
}


def leg_uri(n: int) -> str:
    return f"{OCD}legislatura.rdf/repubblica_{n}"


def sparql(query: str, label: str = "", timeout: int = 120,
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
        print(f"  [{label}] HTTP {e.code}: {body[:120]}")
        return []
    except Exception as e:
        print(f"  [{label}] ERRORE: {e}")
        return []


def val(b: dict, k: str) -> str:
    return b.get(k, {}).get("value", "") or ""


def short(uri: str) -> str:
    return (uri.replace(OCD, "ocd:")
               .replace(DC,   "dc:")
               .replace(DCT,  "dcterms:")
               .replace(RDFS, "rdfs:")
               .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:")
               .replace("http://lod.xdams.org/ontologies/ods/", "ods:")
               .replace("http://xmlns.com/foaf/0.1/", "foaf:"))


def sep(n: int, title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  D{n}. {title}")
    print('=' * 72)


# ── D1. Copertura raw delle proprietà chiave (query diretta, no batch) ────────

def d1_coverage_raw() -> None:
    """Direct COUNT queries for key properties, bypassing VALUES batching.

    The fetch script used VALUES batches of 500 URIs for sub-queries (natura,
    statoIter, versioneTestoAtto). If Leg13-15 return 0% here too, the absence
    is genuine in the triplestore. If they return >0%, the batch approach failed.
    """
    sep(1, "Copertura raw — COUNT diretti per Leg13–16 (senza VALUES batch)")

    props = [
        ("ocd:rif_natura",              f"<{OCD}rif_natura>"),
        ("ocd:rif_statoIter",           f"<{OCD}rif_statoIter>"),
        ("ocd:rif_versioneTestoAtto",   f"<{OCD}rif_versioneTestoAtto>"),
        ("dcterms:isReferencedBy",      f"<{DCT}isReferencedBy>"),
        ("dc:date",                     f"<{DC}date>"),
        ("dc:title",                    f"<{DC}title>"),
    ]

    # Header
    header = f"  {'Proprietà':<35}" + "".join(f"  Leg{l:>2}" for l in LEGS_ALL)
    print(header)
    print("-" * (35 + 9 * len(LEGS_ALL) + 2))

    for prop_name, pred in props:
        row_str = f"  {prop_name:<35}"
        for leg in LEGS_ALL:
            leg_u = leg_uri(leg)
            rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
}}
""", f"{prop_name[:15]} Leg{leg}", silent=True)
            n = val(rows[0], "n") if rows else "ERR"
            row_str += f"  {n:>6}"
            time.sleep(0.4)
        print(row_str)
        time.sleep(0.5)

    time.sleep(1)


# ── D2. Formato dc:identifier per Leg13–16 ────────────────────────────────────

def d2_identifier_format() -> None:
    """Analyze dc:identifier values for Leg13–16 to detect non-integer IDs.

    The fetch script's original keyset used FILTER(xsd:integer(?id) > N), which
    silently drops atti with non-integer dc:identifier (e.g., "105-B", "1061-bis"
    for navette and variants). Fix: keyset on STR(?atto) URI instead.

    This section quantifies how many atti have non-integer dc:identifier per leg.
    """
    sep(2, "Formato dc:identifier — atti con ID non-intero (navette, varianti)")

    print(f"  {'Leg':>4}  {'Tot atti':>10}  {'ID intero':>10}  {'ID non-intero':>14}  {'Campione non-interi'}")
    print("-" * 75)

    for leg in LEGS_ALL:
        leg_u = leg_uri(leg)

        # Total atti
        r_tot = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{ ?atto a ocd:atto ; ocd:rif_leg <{leg_u}> }}
""", f"tot Leg{leg}", silent=True)
        n_tot = int(val(r_tot[0], "n")) if r_tot else -1

        # Atti with integer dc:identifier (regex: only digits)
        r_int = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        dc:identifier ?id .
  FILTER(REGEX(STR(?id), "^[0-9]+$"))
}}
""", f"int Leg{leg}", silent=True)
        n_int = int(val(r_int[0], "n")) if r_int else -1

        # Atti with non-integer dc:identifier
        r_nonint = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?id
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        dc:identifier ?id .
  FILTER(!REGEX(STR(?id), "^[0-9]+$"))
}}
LIMIT 5
""", f"non-int Leg{leg}", silent=True)
        n_nonint = n_tot - n_int if n_tot >= 0 and n_int >= 0 else "?"
        samples   = [val(r, "id") for r in r_nonint][:5]
        sample_s  = str(samples) if samples else "(nessuno)"

        print(f"  {leg:>4}  {n_tot:>10,}  {n_int:>10,}  {str(n_nonint):>14}  {sample_s[:50]}")
        time.sleep(0.8)

    time.sleep(1)


# ── D3. Dump completo di 3 atti campione Leg13 e Leg14 ────────────────────────

def d3_sample_dump() -> None:
    """Dump all properties of 3 sample atti from Leg13 and Leg14.

    Goal: understand if early-legislature atti have a genuinely different structure
    (fewer properties) vs. Leg17 atti, or if they're structurally identical but
    with missing linked-entity data.
    """
    sep(3, "Dump completo atti campione — Leg13 e Leg14 (confronto con Leg17)")

    for leg in [13, 14, 17]:
        leg_u = leg_uri(leg)

        rows_sample = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT DISTINCT ?atto
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> .
}}
ORDER BY ?atto
LIMIT 3
""", f"campione Leg{leg}", silent=True)

        if not rows_sample:
            print(f"\n  ⚠️ Nessun atto trovato per Leg{leg}")
            continue

        print(f"\n  {'─' * 60}")
        print(f"  LEGISLATURA {leg}")
        print(f"  {'─' * 60}")

        seen: set[str] = set()
        for sr in rows_sample[:2]:
            atto_uri = val(sr, "atto")
            if atto_uri in seen:
                continue
            seen.add(atto_uri)

            print(f"\n  ── {atto_uri.split('/')[-1]} ──")
            props = sparql(f"SELECT ?p ?o WHERE {{ <{atto_uri}> ?p ?o }}",
                           "dump", silent=True)
            if not props:
                print("    (nessuna proprietà trovata)")
            for r in props:
                p = short(val(r, "p"))
                o = val(r, "o")
                print(f"    {p:<40}  {o[:75]}")
            time.sleep(0.4)

    time.sleep(1)


# ── D4. Leg16 natura — verifica diretta senza batch ──────────────────────────

def d4_leg16_natura() -> None:
    """Verify Leg16 natura coverage directly and investigate the gap.

    The fetch script reported 82.8% natura for Leg16, with HTTP 400 errors
    on VALUES batches for pages 6-7 and 10-11 (~1,000 atti null).

    Questions:
    - What is the TRUE coverage of ocd:rif_natura for Leg16 (direct query)?
    - Do the atti with null natura have any other distinguishing properties?
    - Is the missing 17.2% concentrated in specific dc:identifier ranges
      (which would confirm the VALUES batch failure hypothesis)?
    """
    sep(4, "Leg16 — verifica natura (diretta), atti senza natura, distribuzione ID")
    leg_u16 = leg_uri(16)

    # Direct count of atti WITH natura
    r_with = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u16}> ;
        ocd:rif_natura ?nat .
}}
""", "Leg16 CON natura", silent=True)
    n_with = int(val(r_with[0], "n")) if r_with else -1

    # Direct count WITHOUT natura
    r_without = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u16}> .
  FILTER NOT EXISTS {{ ?atto ocd:rif_natura ?nat }}
}}
""", "Leg16 SENZA natura", silent=True)
    n_without = int(val(r_without[0], "n")) if r_without else -1

    n_tot = n_with + n_without if n_with >= 0 and n_without >= 0 else "?"
    pct   = n_with / (n_with + n_without) * 100 if isinstance(n_tot, int) and n_tot > 0 else 0

    print(f"\n  Leg16 totale atti:       {n_tot}")
    print(f"  Con ocd:rif_natura:      {n_with}  ({pct:.1f}%)")
    print(f"  Senza ocd:rif_natura:    {n_without}  ({100 - pct:.1f}%)")

    # Sample atti without natura: check their properties
    r_null_nat = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT DISTINCT ?atto ?id ?titolo
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u16}> .
  FILTER NOT EXISTS {{ ?atto ocd:rif_natura ?nat }}
  OPTIONAL {{ ?atto dc:identifier ?id }}
  OPTIONAL {{ ?atto dc:title ?titolo }}
}}
ORDER BY xsd:integer(?id)
LIMIT 10
""", "Leg16 atti senza natura (campione)", silent=True)

    if r_null_nat:
        print(f"\n  Campione atti Leg16 SENZA natura:")
        print(f"  {'id':>8}  {'titolo (troncato)'}")
        for r in r_null_nat:
            id_  = val(r, "id")
            tit  = val(r, "titolo")[:55] or "(nessun titolo)"
            print(f"  {id_:>8}  {tit}")

    # Check if atti without natura also lack other properties → structural gap?
    r_null_props = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT ?prop (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u16}> ;
        ?prop ?val .
  FILTER NOT EXISTS {{ ?atto ocd:rif_natura ?nat }}
}}
GROUP BY ?prop
ORDER BY DESC(?n)
LIMIT 15
""", "props atti Leg16 senza natura", silent=True)

    if r_null_props:
        print(f"\n  Proprietà presenti negli atti Leg16 SENZA natura:")
        for r in r_null_props:
            p = short(val(r, "prop"))
            n = val(r, "n")
            print(f"    {n:>6}  {p}")

    # Distribution of dc:identifier ranges for atti with vs without natura
    print(f"\n  Range dc:identifier atti SENZA natura su Leg16:")
    r_range = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT (MIN(xsd:integer(?id)) AS ?id_min) (MAX(xsd:integer(?id)) AS ?id_max)
       (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u16}> ;
        dc:identifier ?id .
  FILTER(REGEX(STR(?id), "^[0-9]+$"))
  FILTER NOT EXISTS {{ ?atto ocd:rif_natura ?nat }}
}}
""", "range ID senza natura", silent=True)
    if r_range:
        r = r_range[0]
        print(f"  id_min={val(r,'id_min')}  id_max={val(r,'id_max')}  n={val(r,'n')}")
        print("  → Se il range è frammentato (non consecutivo), è bug batch VALUES.")
        print("  → Se è continuo (blocco 2500–3000), è gap strutturale nel triplestore.")

    time.sleep(1)


# ── D5. statoIter e versioneTestoAtto per Leg13–15 ───────────────────────────

def d5_stato_testo_old_legs() -> None:
    """Verify whether ocd:statoIter and ocd:versioneTestoAtto exist at all
    in the triplestore for Leg13–15.

    If COUNT = 0 for all: confirms pre-digital status (no linked entities).
    If COUNT > 0: the fetch script failed to retrieve them (batch size issue).
    Also check if dc:date and dc:title are present (simpler fields).
    """
    sep(5, "statoIter e versioneTestoAtto per Leg13–15 — esistono nel triplestore?")

    for leg in [13, 14, 15, 16]:
        leg_u = leg_uri(leg)
        print(f"\n  Leg{leg}:")

        checks = [
            ("dc:title",                  f"<{DC}title>"),
            ("dc:date",                   f"<{DC}date>"),
            ("dc:type",                   f"<{DC}type>"),
            ("ocd:rif_natura",            f"<{OCD}rif_natura>"),
            ("ocd:rif_statoIter",         f"<{OCD}rif_statoIter>"),
            ("ocd:rif_versioneTestoAtto", f"<{OCD}rif_versioneTestoAtto>"),
            ("dcterms:isReferencedBy",    f"<{DCT}isReferencedBy>"),
            ("ocd:iniziativa",            f"<{OCD}iniziativa>"),
            ("ocd:primo_firmatario",      f"<{OCD}primo_firmatario>"),
        ]
        for name, pred in checks:
            rows = sparql(f"""
PREFIX ocd: <{OCD}>
SELECT (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        {pred} ?val .
}}
""", f"{name[:20]} Leg{leg}", silent=True)
            n = val(rows[0], "n") if rows else "ERR"
            pct_note = ""
            if rows:
                n_int = int(n)
                # Rough expected denominator
                expected = {13: 8281, 14: 7176, 15: 3620, 16: 5820}.get(leg, 1)
                if expected > 0:
                    pct_note = f"  ({n_int / expected * 100:.1f}%)"
            print(f"    {name:<35}  n={n:>6}{pct_note}")
            time.sleep(0.3)

    time.sleep(1)


# ── D6. Distribuzione dc:type per Leg13–16 ───────────────────────────────────

def d6_dctype_distribution() -> None:
    """Distribution of dc:type values for Leg13–16.

    dc:type (e.g. 'Progetto di Legge') is a simple literal present on ~100% of
    Leg17 atti. If it's also ~100% on Leg13–15, the atti are structurally
    complete but simply lack the linked entities (natura, statoIter). This
    would confirm pre-digital status of linked data (not of the atti themselves).
    """
    sep(6, "Distribuzione dc:type per Leg13–16 (campo semplice — baseline strutturale)")

    for leg in [13, 14, 15, 16, 17]:
        leg_u = leg_uri(leg)
        rows = sparql(f"""
PREFIX ocd: <{OCD}>
PREFIX dc: <{DC}>
SELECT ?tipo (COUNT(DISTINCT ?atto) AS ?n)
WHERE {{
  ?atto a ocd:atto ;
        ocd:rif_leg <{leg_u}> ;
        dc:type ?tipo .
}}
GROUP BY ?tipo
ORDER BY DESC(?n)
LIMIT 8
""", f"dc:type Leg{leg}", silent=True)

        expected = {13: 8281, 14: 7176, 15: 3620, 16: 5820, 17: 4903}.get(leg, 1)
        print(f"\n  Leg{leg} — distribuzione dc:type (attesi ~{expected:,} atti):")
        if rows:
            tot = sum(int(val(r, "n")) for r in rows)
            for r in rows:
                n   = int(val(r, "n"))
                tip = val(r, "tipo")
                print(f"    {n:>6,}  ({n / expected * 100:.1f}%)  {tip}")
            print(f"    {'':>6}  tot con dc:type: {tot:,}  ({tot / expected * 100:.1f}%)")
        else:
            print("    (nessun risultato)")
        time.sleep(0.8)

    time.sleep(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verifica copertura reale Leg13–16 nel triplestore Camera."
    )
    parser.add_argument("--section", type=int, default=0,
                        help="Esegui solo sezione D# (0=tutte, default: 0)")
    args = parser.parse_args()

    print("=" * 72)
    print("diag_camera_leg13_16.py — Verifica copertura Leg13–16")
    print(f"Endpoint: {EP}")
    print("=" * 72)
    print()
    print("CONTESTO: fetch_metadati_camera.py ha riportato 0% natura/statoIter/testo")
    print("per Leg13–15 e 82.8% natura per Leg16. Questo script verifica se sono")
    print("valori genuini del triplestore o artefatti del fetch.")

    run = args.section

    if run in (0, 1): d1_coverage_raw()
    if run in (0, 2): d2_identifier_format()
    if run in (0, 3): d3_sample_dump()
    if run in (0, 4): d4_leg16_natura()
    if run in (0, 5): d5_stato_testo_old_legs()
    if run in (0, 6): d6_dctype_distribution()

    print(f"\n{'=' * 72}")
    print("Diagnostica completata.")
    print()
    print("INTERPRETAZIONE ATTESA:")
    print()
    print("  Se D1 mostra 0% natura/statoIter/testo per Leg13–15 anche con query")
    print("  dirette → i dati mancano realmente nel triplestore (pre-digitale).")
    print("  Il fetch è corretto; aggiornare CLAUDE.md §4.7.")
    print()
    print("  Se D1 mostra >0% → il batch VALUES ha fallito silenziosamente.")
    print("  Risolvere aumentando timeout o riducendo batch size.")
    print()
    print("  Se D2 mostra ID non-interi (es. '105-B') → il bug keyset ha escluso")
    print("  quegli atti. Verificare se il totale righe cambia con keyset su URI.")
    print()
    print("  Se D4 mostra natura Leg16 >82.8% con query diretta → il gap è")
    print("  artefatto batch VALUES (HTTP 400). Aggiornare lo script fetch.")
    print("  Se D4 conferma ~82.8% → gap strutturale nel triplestore.")
    print()
    print("  D6: se dc:type è ~100% per Leg13–15 → gli atti esistono e sono")
    print("  strutturalmente completi, ma mancano solo le linked entities")
    print("  (natura, statoIter, versioneTestoAtto). Coerente con pre-digitale.")


if __name__ == "__main__":
    main()
