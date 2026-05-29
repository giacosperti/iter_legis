#!/usr/bin/env python3
"""
fetch_anagrafica_sparql.py — Scarica l'anagrafica senatori tramite SPARQL.

Interroga l'endpoint SPARQL di Open Data Senato (https://dati.senato.it/sparql)
per una o più legislature ed estrae:
  - Dati anagrafici dei senatori (nome, cognome, genere, data di nascita)
  - Storico delle appartenenze ai gruppi parlamentari (con date inizio/fine,
    nome esteso e sigla del gruppo se disponibile)

Produce un JSON compatibile con consolidate_atto.py e flatten_anagrafica.py,
sostituendo il file RDF manuale.

Output JSON per legislatura:
  {
    "senatori": [
      {
        "id": "12345",
        "uri": "http://dati.senato.it/senatore/12345",
        "full_name": "Mario Rossi",
        "first_name": "Mario",
        "last_name": "Rossi",
        "gender": "male",
        "birth_date": "1960-01-01",
        "gruppi": [
          {
            "uri": "...",
            "nome": "Fratelli d'Italia",
            "sigla": "FdI",
            "inizio": "2022-10-13",
            "fine": null
          }
        ]
      }
    ],
    "gruppi": { "http://dati.senato.it/gruppo/xxx": "Fratelli d'Italia" },
    "gruppi_sigle": { "http://dati.senato.it/gruppo/xxx": "FdI" }
  }

Modalità di utilizzo:
  # Singola legislatura con output esplicito
  uv run script_prova/fetch_anagrafica_sparql.py --leg 19 --output data/Leg19/Anagrafica/senatori_19.json

  # Singola legislatura, percorso automatico (data/Leg19/Anagrafica/senatori_19.json)
  uv run script_prova/fetch_anagrafica_sparql.py --leg 19

  # Tutte le legislature (Leg13–Leg19), percorsi automatici
  uv run script_prova/fetch_anagrafica_sparql.py --leg-start 13 --leg-end 19

  # Salta file già esistenti (idempotente)
  uv run script_prova/fetch_anagrafica_sparql.py --leg-start 13 --leg-end 19 --skip-existing

  # Mostra le query SPARQL senza eseguirle
  uv run script_prova/fetch_anagrafica_sparql.py --leg 19 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SPARQL_ENDPOINT = "https://dati.senato.it/sparql"
PAGE_SIZE = 500   # righe per pagina nelle query paginate
RETRY_MAX = 3     # tentativi in caso di errore di rete
RETRY_WAIT = 5    # secondi di attesa tra i tentativi


# ---------------------------------------------------------------------------
# SPARQL helpers
# ---------------------------------------------------------------------------

def sparql_query(query: str, *, dry_run: bool = False) -> list[dict]:
    """
    Esegue una query SPARQL con paginazione automatica via LIMIT/OFFSET.
    Ritorna la lista completa dei binding.
    Se dry_run=True, stampa la query e ritorna lista vuota.
    """
    if dry_run:
        print("--- SPARQL QUERY ---")
        print(query)
        print("--------------------")
        return []

    all_bindings: list[dict] = []
    offset = 0

    while True:
        paginated = f"{query}\nLIMIT {PAGE_SIZE} OFFSET {offset}"
        bindings = _sparql_fetch(paginated)
        all_bindings.extend(bindings)

        if len(bindings) < PAGE_SIZE:
            break   # ultima pagina raggiunta

        offset += PAGE_SIZE
        time.sleep(0.3)  # pausa cortese tra le pagine

    return all_bindings


def _sparql_fetch(query: str) -> list[dict]:
    """Invia una singola richiesta SPARQL e restituisce i binding JSON."""
    params = urllib.parse.urlencode({
        "query": query,
        "format": "application/sparql-results+json",
    })
    url = f"{SPARQL_ENDPOINT}?{params}"

    for attempt in range(1, RETRY_MAX + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/sparql-results+json",
                    "User-Agent": "iter-legis-fetch-anagrafica/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            return data.get("results", {}).get("bindings", [])

        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            if attempt < RETRY_MAX:
                print(f"  ⚠️  Tentativo {attempt}/{RETRY_MAX} fallito: {e} — riprovo tra {RETRY_WAIT}s...")
                time.sleep(RETRY_WAIT)
            else:
                raise RuntimeError(f"SPARQL request fallita dopo {RETRY_MAX} tentativi: {e}") from e

    return []  # unreachable


def _val(binding: dict, key: str) -> str | None:
    """Estrae il valore stringa da un binding SPARQL, o None se assente."""
    entry = binding.get(key)
    if entry is None:
        return None
    return entry.get("value")


# ---------------------------------------------------------------------------
# Query SPARQL
# ---------------------------------------------------------------------------

def query_senatori(leg: int) -> str:
    """Recupera senatori con dati anagrafici per la legislatura specificata."""
    return f"""
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT DISTINCT ?senatore ?label ?nome ?cognome ?genere ?dataNascita
WHERE {{
  ?senatore a osr:Senatore .
  ?senatore ocd:aderisce ?adesione .
  ?adesione osr:legislatura {leg} .
  OPTIONAL {{ ?senatore rdfs:label ?label }}
  OPTIONAL {{ ?senatore foaf:firstName ?nome }}
  OPTIONAL {{ ?senatore foaf:lastName ?cognome }}
  OPTIONAL {{ ?senatore foaf:gender ?genere }}
  OPTIONAL {{ ?senatore osr:dataNascita ?dataNascita }}
}}
ORDER BY ?senatore
"""


def query_gruppi_senatori(leg: int) -> str:
    """Recupera le appartenenze ai gruppi parlamentari per la legislatura."""
    return f"""
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT ?senatore ?gruppo ?gruppoLabel ?inizio ?fine
WHERE {{
  ?senatore a osr:Senatore .
  ?senatore ocd:aderisce ?adesione .
  ?adesione osr:legislatura {leg} .
  ?adesione osr:gruppo ?gruppo .
  OPTIONAL {{ ?adesione osr:inizio ?inizio }}
  OPTIONAL {{ ?adesione osr:fine ?fine }}
  OPTIONAL {{ ?gruppo rdfs:label ?gruppoLabel }}
}}
ORDER BY ?senatore ?inizio
"""


def query_nomi_gruppi() -> str:
    """
    Recupera nomi e sigle dei gruppi parlamentari.

    Note tecniche:
    - Classe: ocd:gruppoParlamentare (non osr:Gruppo)
    - Nomi e sigle sono in blank node: osr:denominazione → osr:titolo / osr:titoloBreve
    - Non filtriamo per legislatura (FILTER EXISTS non supportato da Virtuoso):
      il filtro viene applicato in Python al momento del join
    """
    return """
PREFIX osr: <http://dati.senato.it/osr/>
PREFIX ocd: <http://dati.camera.it/ocd/>

SELECT ?gruppo ?titolo ?titoloBreve ?fine
WHERE {
  ?gruppo a ocd:gruppoParlamentare .
  ?gruppo osr:denominazione ?denom .
  ?denom osr:titolo ?titolo .
  OPTIONAL { ?denom osr:titoloBreve ?titoloBreve }
  OPTIONAL { ?denom osr:fine ?fine }
}
"""


# ---------------------------------------------------------------------------
# Costruzione del JSON di output
# ---------------------------------------------------------------------------

def resolve_group_info(
    gruppo_uri: str,
    nomi_gruppi: dict[str, list[dict]],
    gruppo_label_fallback: str | None,
) -> tuple[str, str | None]:
    """
    Risolve nome e sigla di un gruppo dalla mappa nomi_gruppi.
    Preferisce la denominazione senza data di fine (denominazione corrente).
    Fallback: rdfs:label → URI abbreviata.
    Ritorna (nome, sigla).
    """
    denoms = nomi_gruppi.get(gruppo_uri, [])
    if denoms:
        correnti = [d for d in denoms if d.get("fine") is None]
        ref = correnti[0] if correnti else denoms[-1]
        return ref["titolo"], ref.get("sigla")

    if gruppo_label_fallback:
        return gruppo_label_fallback, None

    return gruppo_uri.split("/")[-1], None


def build_output(
    bindings_senatori: list[dict],
    bindings_gruppi: list[dict],
    bindings_nomi: list[dict],
) -> dict:
    """Costruisce il dizionario JSON finale dai tre set di binding SPARQL."""

    # --- Mappa URI gruppo → lista denominazioni (con sigla) ---
    nomi_gruppi: dict[str, list[dict]] = {}
    for b in bindings_nomi:
        uri = _val(b, "gruppo")
        titolo = _val(b, "titolo")
        sigla = _val(b, "titoloBreve")
        fine = _val(b, "fine")
        if uri and titolo:
            nomi_gruppi.setdefault(uri, []).append({
                "titolo": titolo,
                "sigla": sigla,
                "fine": fine,
            })

    # --- Mappa URI senatore → lista appartenenze gruppo ---
    gruppi_per_senatore: dict[str, list[dict]] = {}
    gruppi_map: dict[str, str] = {}        # URI → nome esteso (compat. consolidate_atto.py)
    gruppi_sigle_map: dict[str, str] = {}  # URI → sigla
    seen_memberships: set[tuple] = set()   # deduplicazione prodotti cartesiani

    for b in bindings_gruppi:
        sen_uri = _val(b, "senatore")
        grp_uri = _val(b, "gruppo")
        grp_label = _val(b, "gruppoLabel")
        inizio = _val(b, "inizio")
        fine = _val(b, "fine")

        if not sen_uri or not grp_uri:
            continue

        dedup_key = (sen_uri, grp_uri, inizio or "", fine or "")
        if dedup_key in seen_memberships:
            continue
        seen_memberships.add(dedup_key)

        nome, sigla = resolve_group_info(grp_uri, nomi_gruppi, grp_label)
        gruppi_map[grp_uri] = nome
        if sigla:
            gruppi_sigle_map[grp_uri] = sigla

        entry: dict = {
            "uri": grp_uri,
            "nome": nome,
            "inizio": inizio,
            "fine": fine,
        }
        if sigla:
            entry["sigla"] = sigla

        gruppi_per_senatore.setdefault(sen_uri, []).append(entry)

    # --- Costruisci lista senatori ---
    senatori: list[dict] = []
    seen: set[str] = set()

    for b in bindings_senatori:
        sen_uri = _val(b, "senatore")
        if not sen_uri or sen_uri in seen:
            continue
        seen.add(sen_uri)

        sen_id = sen_uri.split("/")[-1]
        full_name = _val(b, "label")
        first_name = _val(b, "nome")
        last_name = _val(b, "cognome")

        if not full_name and first_name and last_name:
            full_name = f"{first_name} {last_name}"

        senatori.append({
            "id": sen_id,
            "uri": sen_uri,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "gender": _val(b, "genere"),
            "birth_date": _val(b, "dataNascita"),
            "gruppi": gruppi_per_senatore.get(sen_uri, []),
        })

    output = {"senatori": senatori, "gruppi": gruppi_map}
    if gruppi_sigle_map:
        output["gruppi_sigle"] = gruppi_sigle_map

    return output


# ---------------------------------------------------------------------------
# Fetch di una singola legislatura
# ---------------------------------------------------------------------------

def fetch_leg(leg: int, out_path: Path, *, dry_run: bool, skip_existing: bool) -> bool:
    """
    Scarica e salva l'anagrafica per una singola legislatura.
    Ritorna True se completato con successo, False in caso di errore.
    """
    if skip_existing and out_path.exists():
        print(f"  [Leg{leg}] File già presente — salto ({out_path})")
        return True

    print(f"\n{'─'*50}")
    print(f"Legislatura {leg} → {out_path}")
    print(f"{'─'*50}")

    print("  Query 1/3: dati anagrafici senatori...")
    try:
        b_senatori = sparql_query(query_senatori(leg), dry_run=dry_run)
    except RuntimeError as e:
        print(f"  ✗ Errore: {e}", file=sys.stderr)
        return False

    print("  Query 2/3: appartenenze ai gruppi parlamentari...")
    try:
        b_gruppi = sparql_query(query_gruppi_senatori(leg), dry_run=dry_run)
    except RuntimeError as e:
        print(f"  ✗ Errore: {e}", file=sys.stderr)
        return False

    print("  Query 3/3: nomi e sigle gruppi parlamentari...")
    try:
        b_nomi = sparql_query(query_nomi_gruppi(), dry_run=dry_run)
    except RuntimeError as e:
        print(f"  ⚠️  Query nomi gruppi fallita ({e}) — userò rdfs:label come fallback.")
        b_nomi = []

    if dry_run:
        return True

    output = build_output(b_senatori, b_gruppi, b_nomi)

    n_sen = len(output["senatori"])
    n_con_grp = sum(1 for s in output["senatori"] if s["gruppi"])
    n_grp = len(output["gruppi"])
    n_sigle = len(output.get("gruppi_sigle", {}))

    print(f"\n  Senatori trovati         : {n_sen}")
    print(f"  Con appartenenza gruppo  : {n_con_grp}")
    print(f"  Gruppi distinti          : {n_grp}  (di cui con sigla: {n_sigle})")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  ✅ Salvato in: {out_path}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scarica anagrafica senatori via SPARQL (una o più legislature)"
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--leg", type=int,
        help="Singola legislatura (es. 19). Se omesso, usa --leg-start/--leg-end."
    )
    mode.add_argument(
        "--leg-start", type=int, default=None,
        help="Prima legislatura del range (default: 13)"
    )

    parser.add_argument(
        "--leg-end", type=int, default=19,
        help="Ultima legislatura del range (default: 19, usato con --leg-start)"
    )
    parser.add_argument(
        "--output",
        help="Percorso JSON di output (solo con --leg; default: data/Leg{N}/Anagrafica/senatori_{N}.json)"
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Salta le legislature per cui il file JSON esiste già"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Stampa le query SPARQL senza eseguirle"
    )
    args = parser.parse_args()

    # Determina la lista di legislature da processare
    if args.leg is not None:
        legs = [args.leg]
    else:
        start = args.leg_start if args.leg_start is not None else 13
        legs = list(range(start, args.leg_end + 1))

    # Determina i percorsi di output
    def auto_path(leg: int) -> Path:
        return Path(f"data/Leg{leg}/Anagrafica/senatori_{leg}.json")

    if args.output and len(legs) > 1:
        print("⚠️  --output è valido solo con --leg (singola legislatura).", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[DRY RUN — nessuna richiesta inviata]\n")

    print(f"Legislature da processare: {[f'Leg{n}' for n in legs]}")

    successi, errori = 0, 0

    for leg in legs:
        out_path = Path(args.output) if (args.output and len(legs) == 1) else auto_path(leg)
        ok = fetch_leg(leg, out_path, dry_run=args.dry_run, skip_existing=args.skip_existing)
        if ok:
            successi += 1
        else:
            errori += 1

    if len(legs) > 1:
        print(f"\n{'='*50}")
        print(f"Completato: {successi}/{len(legs)} legislature")
        if errori:
            print(f"Errori: {errori}")

    return 0 if errori == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
