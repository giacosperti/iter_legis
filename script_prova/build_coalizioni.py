#!/usr/bin/env python3
"""
build_coalizioni.py — Tabella lookup governi/coalizioni Senato Italiano, Leg13–Leg19.

Produce un CSV con una riga per (legislatura × gruppo parlamentare) con le colonne:
  legislatura    : numero legislatura (intero)
  pol_party      : sigla/nome del gruppo (titoloBreve da endpoint SPARQL dati.senato.it)
  sigla          : uguale a pol_party (titoloBreve IS la sigla ufficiale in questo dataset)
  giornialgoverno: giorni totali in cui il gruppo era in coalizione di maggioranza
  governo        : numero di governi in cui il gruppo era in maggioranza nella legislatura
  giornipm       : giorni in cui il gruppo esprimeva il Presidente del Consiglio
  primoministro  : dummy 1/0 — il gruppo esprimeva il Premier in almeno un governo
  governo_nome   : nomi dei governi (separati da ";") in cui il gruppo era in maggioranza
  maggioranza    : dummy 1/0 — il gruppo era in maggioranza in almeno un governo

Nota sui nomi di gruppo:
  I valori di pol_party/sigla sono i titoloBreve restituiti dall'endpoint SPARQL
  dati.senato.it (property osr:titoloBreve di ocd:gruppoParlamentare) e coincidono
  esattamente con quelli usati nei file senatori_{N}.json generati da
  fetch_anagrafica_sparql.py. Per le legislature più datate (Leg13–15) i titoloBreve
  potrebbero non essere disponibili nel SPARQL: in tal caso pol_party = nome usato nel
  sistema SPARQL (osr:titolo), che funge anche da sigla identificativa.

Fonti per i dati storici sui governi:
  - Date ufficiali di insediamento e dimissioni:
      https://www.quirinale.it/page/governirepubblica
  - Composizione delle coalizioni di maggioranza (partiti e liste):
      https://it.wikipedia.org/wiki/Governi_della_Repubblica_Italiana
      Pagine individuali: Governo_Prodi_I, Governo_D%27Alema_I, Governo_D%27Alema_II,
      Governo_Amato_II, Governo_Berlusconi_II, Governo_Berlusconi_III, Governo_Prodi_II,
      Governo_Berlusconi_IV, Governo_Monti, Governo_Letta, Governo_Renzi,
      Governo_Gentiloni, Governo_Conte_I, Governo_Conte_II, Governo_Draghi,
      Governo_Meloni
  - Verifica corrispondenza partiti → gruppi parlamentari Senato:
      Endpoint SPARQL https://dati.senato.it/sparql
      (script fetch_anagrafica_sparql.py in questo progetto)
  - Dati numerici di supporto:
      https://www.camera.it/leg*/568?scheda=... (composizione gruppi per legislatura)

Usage:
  uv run script_prova/build_coalizioni.py
  uv run script_prova/build_coalizioni.py --out data/coalizioni_leg13_19.csv
  uv run script_prova/build_coalizioni.py --leg 19
  uv run script_prova/build_coalizioni.py --leg-start 15 --leg-end 18
  uv run script_prova/build_coalizioni.py --validate
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path


# ============================================================
# CONFIGURAZIONE
# ============================================================

DATA_DIR = Path("data")

FIELDNAMES = [
    "legislatura", "pol_party", "sigla",
    "giornialgoverno", "governo", "giornipm", "primoministro",
    "governo_nome", "maggioranza",
]


# ============================================================
# GRUPPI PARLAMENTARI PER LEGISLATURA
# Fonte: endpoint SPARQL https://dati.senato.it/sparql
#   (query su ocd:gruppoParlamentare, property osr:titoloBreve)
#   generati/verificati tramite fetch_anagrafica_sparql.py
# ============================================================

ALL_GROUPS: dict[int, list[str]] = {
    13: [
        "AN",                # Alleanza Nazionale
        "Comunista",         # Rifondazione Comunista (RC)
        "Democrazia Europea",# Democrazia Europea (Buttiglione)
        "DS-U",              # Democratici di Sinistra-L'Ulivo
        "FI",                # Forza Italia
        "LSP-PSd'Az",        # Lega Nord / Lega per le Autonomie - PSd'Az
        "Misto",             # Gruppo Misto
        "PPI",               # Partito Popolare Italiano
        "Rin.Ld.Ind-Pop.",   # Rinnovamento, Liberaldemocratici, Indip.-Popolari
        "Rinnovam.Ital.",    # Rinnovamento Italiano (Dini)
        "Rinn.Ital.e.Ind.",  # Rinnovamento Italiano e Indipendenti
        "UDEUR",             # Unione Democratici per l'Europa (Mastella)
        "UDC",               # Unione dei Democratici Cristiani
        "Verdi-Un",          # Verdi-L'Ulivo
    ],
    14: [
        "AN",                # Alleanza Nazionale
        "Aut",               # Autonomie (SVP, UV, MAIE e altri)
        "DS-U",              # Democratici di Sinistra-L'Ulivo
        "FI",                # Forza Italia
        "LSP-PSd'Az",        # Lega Nord / Lega per le Autonomie - PSd'Az
        "Mar-DL-U",          # Margherita-Democrazia è Libertà-L'Ulivo
        "Misto",             # Gruppo Misto
        "UDC",               # Unione dei Democratici Cristiani
        "Verdi-Un",          # Verdi-L'Ulivo
    ],
    15: [
        "AN",                # Alleanza Nazionale
        "Aut",               # Autonomie (SVP e altri)
        "DCA-PRI-MPA",       # DCA-PRI-MPA (centro-destra, De Michelis/MPA)
        "FI",                # Forza Italia
        "IU-Verdi-Com",      # Insieme con l'Unione (Verdi + Comunisti Italiani)
        "LSP-PSd'Az",        # Lega Nord / Lega per le Autonomie - PSd'Az
        "Misto",             # Gruppo Misto
        "PD-IDP",            # Partito Democratico-L'Ulivo (poi PD)
        "RC-SE",             # Rifondazione Comunista-Sinistra Europea
        "SDSE",              # Socialisti Democratici – Sinistra Europea (PDCI)
        "UDC",               # Unione dei Democratici Cristiani
    ],
    16: [
        "CN:GS-SI-PID-IB-FI",           # Grande Sud e altri (centro-destra minore)
        "FDI-CDN",                       # Fratelli d'Italia - Centro destra nazionale
        "FI-BP-PPE",                     # PdL / Forza Italia - Berlusconi Pres. - PPE
        "FLI",                           # Futuro e Libertà per l'Italia (Fini)
        "IdV",                           # Italia dei Valori (Di Pietro)
        "LSP-PSd'Az",                    # Lega Nord / Lega per le Autonomie - PSd'Az
        "Misto",                         # Gruppo Misto
        "PD-IDP",                        # Partito Democratico
        "Per il Terzo Polo:ApI-FLI-CD",  # Terzo Polo (Casini, Fini, Cesa)
        "UDC-SVP-AUT:UV-MAIE-VN-MRE-PLI-PSI",  # UDC e Autonomie varie
    ],
    17: [
        "ALA-PRI",           # Alleanza Liberalpopolare Autonomie - PRI
        "AP-CpE-NCD",        # Area Popolare (NCD + UDC)
        "Art.1-MDP-LeU",     # Articolo 1 - MDP - LeU
        "Aut(SVP-PATT,Cb)",  # Autonomie (SVP, PATT, Autonomisti)
        "CoR",               # Conservatori e Riformisti
        "FL(Id-PL,PLI)",     # Federazione della Libertà (Ids, PLI)
        "FI-BP-PPE",         # Forza Italia - Berlusconi Presidente - PPE
        "GAL-UDC",           # Grandi Autonomie e Libertà - UDC
        "LSP-PSd'Az",        # Lega Nord / Lega per le Autonomie - PSd'Az
        "Misto",             # Gruppo Misto
        "M5S",               # MoVimento 5 Stelle
        "NcI",               # Noi con l'Italia
        "PD-IDP",            # Partito Democratico
        "PI",                # Per l'Italia (Mauro)
        "SCpI",              # Scelta Civica per l'Italia
    ],
    18: [
        "Aut(SVP-PATT,Cb)",               # Autonomie
        "C.A.L.-Idv",                     # Coraggio Italia / Cambiamo! e altri
        "Europeisti-MAIE-CD",             # Europeisti-MAIE-CD
        "FI-BP-PPE",                      # Forza Italia - Berlusconi Presidente - PPE
        "FdI",                            # Fratelli d'Italia
        "Ipf-CD",                         # Insieme per il Futuro - CD (Di Maio)
        "IV-PSI",                         # Italia Viva - PSI
        "LSP-PSd'Az",                     # Lega - PSd'Az
        "Misto",                          # Gruppo Misto
        "M5S",                            # MoVimento 5 Stelle
        "PD-IDP",                         # Partito Democratico
        "UpC-CAL-Alt-PC-AI-Pr.SMART-IdV", # Unione Popolare e altri minori
    ],
    19: [
        "Aut(SVP-PATT,Cb)",                   # Autonomie
        "Cd'I-UDC-NM(NcI,CI,IaC)-MAIE-CP",  # Noi Moderati e altri (centro-dx minore)
        "FI-BP-PPE",                           # Forza Italia - Berlusconi Presidente - PPE
        "FdI",                                 # Fratelli d'Italia
        "IV-C-RE",                             # Italia Viva - Azione - Renew Europe
        "LSP-PSd'Az",                          # Lega - PSd'Az
        "Misto",                               # Gruppo Misto
        "M5S",                                 # MoVimento 5 Stelle
        "PD-IDP",                              # Partito Democratico
    ],
}


# ============================================================
# GOVERNI PER LEGISLATURA
# ============================================================
# Ogni governo ha:
#   nome       : nome storico del governo
#   inizio     : data di insediamento (YYYY-MM-DD)
#   fine       : data di fine (YYYY-MM-DD), o None per governo in carica
#   pm_gruppo  : sigla ESATTA del gruppo SPARQL che esprime il PM (None = tecnico)
#   maggioranza: insieme delle sigle ESATTE dei gruppi SPARQL in coalizione
#
# FONTI:
#   Date: https://www.quirinale.it/page/governirepubblica
#   Coalizioni: https://it.wikipedia.org/wiki/Governi_della_Repubblica_Italiana
#   Verifica gruppi: endpoint SPARQL dati.senato.it + fetch_anagrafica_sparql.py

GOVERNI: dict[int, list[dict]] = {

    # --- LEGISLATURA 13 (9 mag 1996 – 29 mag 2001) ---
    13: [
        {
            "nome": "Prodi I",
            "inizio": "1996-05-17",
            "fine":   "1998-10-21",
            # Romano Prodi — centrosinistra (Ulivo); gruppo di riferimento DS-U
            # Fonti: https://it.wikipedia.org/wiki/Governo_Prodi_I
            #        https://www.quirinale.it/elementi/6593
            "pm_gruppo": "DS-U",
            "maggioranza": {
                "DS-U",              # Democratici di Sinistra
                "PPI",               # Partito Popolare Italiano
                "Rinnovam.Ital.",    # Rinnovamento Italiano (Dini)
                "Rinn.Ital.e.Ind.", # Rinnovamento Italiano e Indipendenti
                "Verdi-Un",          # Verdi
                "Rin.Ld.Ind-Pop.",   # Rinnovamento, Libdem, Indip.-Popolari
            },
        },
        {
            "nome": "D'Alema I",
            "inizio": "1998-10-21",
            "fine":   "1999-12-22",
            # Massimo D'Alema — DS-U
            # Fonte: https://it.wikipedia.org/wiki/Governo_D%27Alema_I
            "pm_gruppo": "DS-U",
            "maggioranza": {
                "DS-U", "PPI", "Rinnovam.Ital.", "Rinn.Ital.e.Ind.",
                "UDEUR",             # Unione Democratici per l'Europa (Mastella)
                "Democrazia Europea",
            },
        },
        {
            "nome": "D'Alema II",
            "inizio": "1999-12-22",
            "fine":   "2000-04-26",
            # Massimo D'Alema — DS-U (rimpasto)
            # Fonte: https://it.wikipedia.org/wiki/Governo_D%27Alema_II
            "pm_gruppo": "DS-U",
            "maggioranza": {
                "DS-U", "PPI", "Rinnovam.Ital.",
                "UDEUR", "Democrazia Europea",
            },
        },
        {
            "nome": "Amato II",
            "inizio": "2000-04-26",
            "fine":   "2001-06-11",
            # Giuliano Amato — tecnico centrosinistra; conv. associato a DS-U
            # Fonte: https://it.wikipedia.org/wiki/Governo_Amato_II
            "pm_gruppo": "DS-U",
            "maggioranza": {
                "DS-U", "PPI", "UDEUR", "Democrazia Europea", "Verdi-Un",
            },
        },
    ],

    # --- LEGISLATURA 14 (30 mag 2001 – 27 apr 2006) ---
    14: [
        {
            "nome": "Berlusconi II",
            "inizio": "2001-06-11",
            "fine":   "2005-04-20",
            # Silvio Berlusconi — FI (Casa delle Libertà)
            # Fonte: https://it.wikipedia.org/wiki/Governo_Berlusconi_II
            "pm_gruppo": "FI",
            "maggioranza": {"FI", "AN", "LSP-PSd'Az", "UDC", "Aut"},
        },
        {
            "nome": "Berlusconi III",
            "inizio": "2005-04-20",
            "fine":   "2006-05-17",
            # Silvio Berlusconi — FI (rimpasto, stessa coalizione)
            # Fonte: https://it.wikipedia.org/wiki/Governo_Berlusconi_III
            "pm_gruppo": "FI",
            "maggioranza": {"FI", "AN", "LSP-PSd'Az", "UDC", "Aut"},
        },
    ],

    # --- LEGISLATURA 15 (28 apr 2006 – 28 apr 2008) ---
    15: [
        {
            "nome": "Prodi II",
            "inizio": "2006-05-17",
            "fine":   "2008-05-08",
            # Romano Prodi — PD-IDP (L'Unione)
            # Fonte: https://it.wikipedia.org/wiki/Governo_Prodi_II
            "pm_gruppo": "PD-IDP",
            "maggioranza": {
                "PD-IDP",        # Ulivo/PD
                "RC-SE",         # Rifondazione Comunista
                "IU-Verdi-Com",  # Verdi + Comunisti Italiani
                "SDSE",          # Socialisti Democratici - SE
                "Aut",           # SVP e altri autonomisti
            },
        },
    ],

    # --- LEGISLATURA 16 (29 apr 2008 – 14 mar 2013) ---
    16: [
        {
            "nome": "Berlusconi IV",
            "inizio": "2008-05-08",
            "fine":   "2011-11-16",
            # Silvio Berlusconi — FI-BP-PPE (PdL + Lega)
            # Fonte: https://it.wikipedia.org/wiki/Governo_Berlusconi_IV
            "pm_gruppo": "FI-BP-PPE",
            "maggioranza": {
                "FI-BP-PPE",
                "LSP-PSd'Az",
                "CN:GS-SI-PID-IB-FI",   # Grande Sud e gruppi affini
            },
        },
        {
            "nome": "Monti",
            "inizio": "2011-11-16",
            "fine":   "2013-04-28",
            # Mario Monti — governo tecnico di larghe intese
            # Fonte: https://it.wikipedia.org/wiki/Governo_Monti
            "pm_gruppo": None,   # governo tecnico: nessun gruppo esprime il PM
            "maggioranza": {
                "PD-IDP",
                "FI-BP-PPE",
                "UDC-SVP-AUT:UV-MAIE-VN-MRE-PLI-PSI",
                "Per il Terzo Polo:ApI-FLI-CD",
            },
        },
    ],

    # --- LEGISLATURA 17 (15 mar 2013 – 22 mar 2018) ---
    17: [
        {
            "nome": "Letta",
            "inizio": "2013-04-28",
            "fine":   "2014-02-22",
            # Enrico Letta — PD-IDP (governo di larghe intese)
            # Fonte: https://it.wikipedia.org/wiki/Governo_Letta
            "pm_gruppo": "PD-IDP",
            "maggioranza": {
                "PD-IDP", "AP-CpE-NCD", "GAL-UDC",
                "SCpI", "PI", "Aut(SVP-PATT,Cb)",
            },
        },
        {
            "nome": "Renzi",
            "inizio": "2014-02-22",
            "fine":   "2016-12-12",
            # Matteo Renzi — PD-IDP
            # Fonte: https://it.wikipedia.org/wiki/Governo_Renzi
            "pm_gruppo": "PD-IDP",
            "maggioranza": {
                "PD-IDP", "AP-CpE-NCD", "GAL-UDC",
                "Aut(SVP-PATT,Cb)", "ALA-PRI", "NcI",
            },
        },
        {
            "nome": "Gentiloni",
            "inizio": "2016-12-12",
            "fine":   "2018-06-01",
            # Paolo Gentiloni — PD-IDP
            # Fonte: https://it.wikipedia.org/wiki/Governo_Gentiloni
            "pm_gruppo": "PD-IDP",
            "maggioranza": {
                "PD-IDP", "AP-CpE-NCD", "GAL-UDC",
                "Aut(SVP-PATT,Cb)", "ALA-PRI", "NcI",
            },
        },
    ],

    # --- LEGISLATURA 18 (23 mar 2018 – 12 ott 2022) ---
    18: [
        {
            "nome": "Gentiloni (reggenza)",
            "inizio": "2018-03-23",   # insediamento nuovo Parlamento
            "fine":   "2018-06-01",
            # Paolo Gentiloni — governo uscente per gli affari correnti
            # (elezioni 4 mar 2018; nuovo Parlamento insediato 23 mar 2018)
            "pm_gruppo": "PD-IDP",
            "maggioranza": {"PD-IDP", "Aut(SVP-PATT,Cb)"},
        },
        {
            "nome": "Conte I",
            "inizio": "2018-06-01",
            "fine":   "2019-09-05",
            # Giuseppe Conte — M5S + Lega ("governo del cambiamento")
            # PM tecnico proposto da M5S; gruppo di riferimento M5S
            # Fonte: https://it.wikipedia.org/wiki/Governo_Conte_I
            "pm_gruppo": "M5S",
            "maggioranza": {"M5S", "LSP-PSd'Az"},
        },
        {
            "nome": "Conte II",
            "inizio": "2019-09-05",
            "fine":   "2021-02-13",
            # Giuseppe Conte — M5S + PD + Italia Viva
            # Fonte: https://it.wikipedia.org/wiki/Governo_Conte_II
            "pm_gruppo": "M5S",
            "maggioranza": {
                "M5S", "PD-IDP", "IV-PSI", "Europeisti-MAIE-CD",
            },
        },
        {
            "nome": "Draghi",
            "inizio": "2021-02-13",
            "fine":   "2022-10-22",
            # Mario Draghi — governo tecnico di unità nazionale
            # Fonte: https://it.wikipedia.org/wiki/Governo_Draghi
            "pm_gruppo": None,   # governo tecnico
            "maggioranza": {
                "PD-IDP", "M5S", "LSP-PSd'Az", "FI-BP-PPE",
                "IV-PSI", "Aut(SVP-PATT,Cb)", "Europeisti-MAIE-CD", "Ipf-CD",
            },
        },
    ],

    # --- LEGISLATURA 19 (13 ott 2022 – in corso) ---
    19: [
        {
            "nome": "Meloni",
            "inizio": "2022-10-22",
            "fine":   None,   # legislatura in corso → calcolato come data odierna
            # Giorgia Meloni — FdI (centrodestra)
            # Fonte: https://it.wikipedia.org/wiki/Governo_Meloni
            "pm_gruppo": "FdI",
            "maggioranza": {
                "FdI", "FI-BP-PPE", "LSP-PSd'Az",
                "Cd'I-UDC-NM(NcI,CI,IaC)-MAIE-CP",
            },
        },
    ],
}


# ============================================================
# FUNZIONI DI SUPPORTO
# ============================================================

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def days_between(start: str, end: str | None) -> int:
    """Calcola i giorni tra start e end (None = oggi)."""
    d_start = parse_date(start)
    d_end = date.today() if end is None else parse_date(end)
    return max(0, (d_end - d_start).days)


def load_sigla_map(leg: int) -> dict[str, str]:
    """
    Carica da senatori_{leg}.json la mappa titoloBreve → titoloBreve (identità)
    oppure titoloBreve → titolo (nome lungo), a seconda di quanto disponibile.

    In questo dataset pol_party == titoloBreve == sigla, quindi la mappa è
    usata principalmente per validare la disponibilità dei dati JSON.

    Ritorna dict vuoto se il file non esiste (usato come warning).
    """
    json_path = DATA_DIR / f"Leg{leg}" / "Anagrafica" / f"senatori_{leg}.json"
    if not json_path.exists():
        return {}
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        gruppi      = data.get("gruppi", {})        # {uri: titolo (lungo)}
        sigle_map   = data.get("gruppi_sigle", {})  # {uri: titoloBreve}
        # Costruisce: titoloBreve → titolo (per riferimento futuro)
        result: dict[str, str] = {}
        for uri, titolo in gruppi.items():
            sigla = sigle_map.get(uri)
            if sigla:
                result[sigla] = titolo
        return result
    except (json.JSONDecodeError, KeyError, OSError):
        return {}


def validate_data(legs: list[int]) -> bool:
    """
    Controlla che tutti i gruppi in ogni set 'maggioranza' e 'pm_gruppo'
    siano presenti in ALL_GROUPS per quella legislatura.
    Ritorna True se tutto ok.
    """
    print("=== Validazione dati coalizioni ===")
    ok = True
    for leg in legs:
        known = set(ALL_GROUPS.get(leg, []))
        for gov in GOVERNI.get(leg, []):
            for g in gov["maggioranza"]:
                if g not in known:
                    print(f"  ⚠️  Leg{leg}/{gov['nome']}: "
                          f"gruppo '{g}' non in ALL_GROUPS")
                    ok = False
            pm = gov.get("pm_gruppo")
            if pm and pm not in known:
                print(f"  ⚠️  Leg{leg}/{gov['nome']}: "
                      f"pm_gruppo '{pm}' non in ALL_GROUPS")
                ok = False
    if ok:
        print("  ✅ Tutti i gruppi nelle coalizioni sono presenti in ALL_GROUPS.")
    return ok


def build_rows(leg: int, governi: list[dict], groups: list[str]) -> list[dict]:
    """
    Costruisce le righe CSV per una legislatura.
    Una riga per gruppo parlamentare.
    """
    rows: list[dict] = []
    for group in groups:
        giorni_gov = 0
        n_governi  = 0
        giorni_pm  = 0
        is_pm      = 0
        gov_names: list[str] = []

        for gov in governi:
            dur     = days_between(gov["inizio"], gov.get("fine"))
            in_mag  = group in gov["maggioranza"]
            is_pm_g = (group == gov.get("pm_gruppo"))

            if in_mag:
                giorni_gov += dur
                n_governi  += 1
                gov_names.append(gov["nome"])

            if is_pm_g:
                giorni_pm += dur
                is_pm = 1

        rows.append({
            "legislatura":     leg,
            "pol_party":       group,
            "sigla":           group,   # titoloBreve == sigla in questo dataset
            "giornialgoverno": giorni_gov,
            "governo":         n_governi,
            "giornipm":        giorni_pm,
            "primoministro":   is_pm,
            "governo_nome":    ";".join(gov_names) if gov_names else "",
            "maggioranza":     1 if giorni_gov > 0 else 0,
        })
    return rows


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build tabella lookup coalizioni/governi Leg13–Leg19 (Senato)"
    )
    parser.add_argument("--leg",       type=int, help="Sola legislatura (es. 19)")
    parser.add_argument("--leg-start", type=int, default=13)
    parser.add_argument("--leg-end",   type=int, default=19)
    parser.add_argument("--out",       default="data/coalizioni_leg13_19.csv")
    parser.add_argument(
        "--validate", action="store_true",
        help="Esegui solo validazione interna dei dati, senza scrivere il CSV",
    )
    args = parser.parse_args()

    legs = [args.leg] if args.leg else list(range(args.leg_start, args.leg_end + 1))

    # --- Validazione ---
    all_ok = validate_data(legs)
    print()
    if args.validate:
        return 0 if all_ok else 1

    # --- Costruzione righe ---
    all_rows: list[dict] = []

    for leg in legs:
        governi = GOVERNI.get(leg)
        groups  = ALL_GROUPS.get(leg)

        if not governi:
            print(f"⚠️  Leg{leg}: nessun dato governi — salto")
            continue
        if not groups:
            print(f"⚠️  Leg{leg}: nessun dato gruppi — salto")
            continue

        # Controlla se il JSON è disponibile (solo informativo)
        sigla_map = load_sigla_map(leg)
        json_status = (f"JSON OK ({len(sigla_map)} gruppi)"
                       if sigla_map else "JSON non trovato")

        rows = build_rows(leg, governi, groups)
        all_rows.extend(rows)

        n_mag = sum(1 for r in rows if r["maggioranza"] == 1)
        n_opp = len(rows) - n_mag
        n_gov = len(governi)

        print(
            f"[Leg{leg}] Governi: {n_gov}  |  "
            f"Gruppi totali: {len(rows)}  |  "
            f"Maggioranza: {n_mag}  |  Opposizione: {n_opp}  |  {json_status}"
        )

    # --- Scrivi CSV ---
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n✅ Salvato: {out_path}  ({len(all_rows)} righe, "
          f"{len(legs)} legislature)")

    # Riepilogo: quanti gruppi in maggioranza vs opposizione totale
    n_tot_mag = sum(1 for r in all_rows if r["maggioranza"] == 1)
    n_tot_opp = len(all_rows) - n_tot_mag
    print(f"   Righe in maggioranza: {n_tot_mag}  |  In opposizione: {n_tot_opp}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
