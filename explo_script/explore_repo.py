#!/usr/bin/env python3
"""
explore_repo.py — Inventario degli atti nel repository AkomaNtosoBulkData del Senato.

Per ogni legislatura nel range specificato (default Leg13–Leg19), elenca tutti gli atti
e rileva quali sottocartelle sono presenti (ddlpres, ddlcomm, ddlmess, emend, emendc,
resaula, sommcomm).

Strategia: approccio a due livelli tramite Contents API GitHub.
  - Livello 1: lista degli atti per legislatura  (1 chiamata per legislatura)
  - Livello 2: sottocartelle di ogni atto        (1 chiamata per atto)

Sistema di checkpoint:
  - Dopo ogni atto processato, il progresso viene salvato in un file JSON
    (default: data/repo_inventory.checkpoint.json)
  - Se lo script viene interrotto (Ctrl+C o crash), al riavvio riprende
    automaticamente dall'atto successivo all'ultimo salvato
  - Il checkpoint viene cancellato automaticamente al completamento
  - Usa --reset per ignorare il checkpoint e ripartire da zero

Richiede gh CLI autenticato (gh auth login).

Output:
  - Progresso su stdout
  - CSV inventario: data/repo_inventory.csv (configurabile con --out)

Usage:
  uv run script_prova/explore_repo.py
  uv run script_prova/explore_repo.py --leg-start 19 --leg-end 19     # test su Leg19
  uv run script_prova/explore_repo.py --reset                          # ignora checkpoint
  uv run script_prova/explore_repo.py --out data/repo_inventory.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OWNER = "SenatoDellaRepubblica"
REPO = "AkomaNtosoBulkData"
REF = "master"

INTERESTING_DIRS = {"ddlpres", "ddlcomm", "ddlmess", "emend", "emendc", "resaula", "sommcomm"}

# Pausa cortese tra chiamate API (200ms = ~300 req/min, ben sotto i 5000/ora di gh)
API_DELAY = 0.2


# ---------------------------------------------------------------------------
# Checkpoint: load / save / clear
# ---------------------------------------------------------------------------

def checkpoint_path_from_out(out: str) -> Path:
    p = Path(out)
    return p.parent / (p.stem + ".checkpoint.json")


def load_checkpoint(cp_path: Path) -> dict | None:
    """Carica il checkpoint se esiste e è valido, altrimenti ritorna None."""
    if not cp_path.exists():
        return None
    try:
        with open(cp_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"  ⚠️  Checkpoint corrotto o illeggibile ({cp_path}) — verrà ignorato.")
        return None


def save_checkpoint(cp_path: Path, data: dict) -> None:
    """
    Salva il checkpoint in modo atomico: scrive su un file .tmp e poi lo rinomina.
    Se lo script si interrompe durante la scrittura, il file precedente rimane intatto.
    """
    cp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cp_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp_path, cp_path)   # atomico su Unix e Windows


def clear_checkpoint(cp_path: Path) -> None:
    """Rimuove il file di checkpoint al completamento."""
    if cp_path.exists():
        cp_path.unlink()


# ---------------------------------------------------------------------------
# GitHub API via gh CLI
# ---------------------------------------------------------------------------

def gh_api(endpoint: str, *, timeout: int = 30) -> list | dict | None:
    """
    Chiama l'API GitHub tramite gh CLI autenticato.
    Ritorna il JSON parsato, o None in caso di 404 (directory non esistente).
    """
    cmd = [
        "gh", "api", endpoint,
        "--header", "Accept: application/vnd.github+json",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout ({timeout}s) su: {endpoint}")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "404" in stderr or "Not Found" in stderr:
            return None
        raise RuntimeError(f"gh api error [{endpoint}]: {stderr}")

    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Livello 1: lista atti per legislatura  (Git Tree API, non-recursive)
# ---------------------------------------------------------------------------
#
# La Contents API di GitHub restituisce al massimo 1000 item per directory
# indipendentemente dal parametro per_page, rendendo impossibile la vera
# paginazione per directory grandi (es. Leg19 ha >1000 atti).
# La Git Tree API non-recursive non ha questo limite:
#   1. Recupera il tree SHA della legislatura dalla root del repo  (1 chiamata)
#   2. Recupera l'elenco completo di tutti gli item della cartella (1 chiamata)
# Nessuna paginazione necessaria; nessun timeout (non è recursive).

def _get_root_tree(timeout: int = 30) -> list[dict]:
    """Recupera il tree di primo livello del repo (gli item root, non-recursive)."""
    data = gh_api(f"repos/{OWNER}/{REPO}/git/trees/{REF}", timeout=timeout)
    if data is None or "tree" not in data:
        raise RuntimeError(f"Impossibile leggere il tree root (ref={REF})")
    return data["tree"]


def list_leg_atti(leg_name: str) -> list[str]:
    """
    Ritorna la lista degli ID atto (Atto*) per una legislatura.
    Usa la Git Tree API (non-recursive): 2 chiamate totali per legislatura.
    """
    # Step 1 — trova il SHA del tree della legislatura nella root
    root_items = _get_root_tree()
    leg_sha: str | None = None
    for item in root_items:
        if item.get("path") == leg_name and item.get("type") == "tree":
            leg_sha = item["sha"]
            break

    if leg_sha is None:
        return []   # legislatura non presente nel repo

    # Step 2 — recupera tutti gli item diretti della cartella Leg{N}
    time.sleep(API_DELAY)
    data = gh_api(
        f"repos/{OWNER}/{REPO}/git/trees/{leg_sha}",
        timeout=60,
    )
    if data is None or "tree" not in data:
        raise RuntimeError(f"Impossibile leggere il tree di {leg_name}")

    if data.get("truncated"):
        # >100 000 item nella cartella: caso improbabile, ma lo segnaliamo
        print(f"\n  ⚠️  Tree {leg_name} troncato (>100 000 item) — lista incompleta")

    atti = [
        item["path"]
        for item in data["tree"]
        if item.get("type") == "tree" and item["path"].startswith("Atto")
    ]
    return sorted(atti)


# ---------------------------------------------------------------------------
# Livello 2: sottocartelle di un singolo atto
# ---------------------------------------------------------------------------

def list_atto_subdirs(leg_name: str, atto_id: str) -> set[str]:
    """Ritorna l'insieme dei nomi di sottocartella presenti in un atto."""
    endpoint = f"repos/{OWNER}/{REPO}/contents/{leg_name}/{atto_id}?ref={REF}"
    data = gh_api(endpoint, timeout=20)

    if data is None or not isinstance(data, list):
        return set()

    return {item["name"] for item in data if item["type"] == "dir"}


# ---------------------------------------------------------------------------
# Record e summary
# ---------------------------------------------------------------------------

def build_record(leg_num: int, atto_id: str, subdirs: set[str]) -> dict:
    record: dict = {"legislatura": leg_num, "atto_id": atto_id}
    for d in sorted(INTERESTING_DIRS):
        record[f"has_{d}"] = d in subdirs
    return record


def print_leg_summary(leg_num: int, records: list[dict]) -> None:
    n = len(records)
    n_emend = sum(1 for r in records if r["has_emend"] or r["has_emendc"])
    n_proc = sum(
        1 for r in records if r["has_ddlpres"] and (r["has_emend"] or r["has_emendc"])
    )
    print(f"\n  {'─'*42}")
    print(f"  Leg{leg_num} — riepilogo")
    print(f"    Atti totali              : {n}")
    print(f"    Con emendamenti          : {n_emend}  (emend o emendc)")
    print(f"    Processabili             : {n_proc}  (ddlpres + emend/emendc)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventario atti nel repo AkomaNtosoBulkData del Senato"
    )
    parser.add_argument("--leg-start", type=int, default=13)
    parser.add_argument("--leg-end",   type=int, default=19)
    parser.add_argument("--out",   default="data/repo_inventory.csv")
    parser.add_argument(
        "--reset", action="store_true",
        help="Ignora il checkpoint esistente e riparte da zero"
    )
    args = parser.parse_args()

    cp_path = checkpoint_path_from_out(args.out)

    # --- Gestione checkpoint ---
    checkpoint: dict = {}

    if args.reset and cp_path.exists():
        cp_path.unlink()
        print("Checkpoint rimosso. Ripartenza da zero.\n")

    existing = load_checkpoint(cp_path)

    if existing:
        # Verifica compatibilità parametri
        if (existing.get("leg_start") != args.leg_start or
                existing.get("leg_end") != args.leg_end):
            print(
                f"⚠️  Il checkpoint esistente usa parametri diversi "
                f"(Leg{existing.get('leg_start')}–Leg{existing.get('leg_end')}).\n"
                f"   Usa --reset per ignorarlo e ripartire con i parametri attuali."
            )
            return 1

        checkpoint = existing
        n_done = len(checkpoint.get("records", []))
        print(
            f"=== Ripresa da checkpoint — {n_done} atti già processati ===\n"
            f"    ({cp_path})\n"
        )
    else:
        checkpoint = {
            "leg_start": args.leg_start,
            "leg_end": args.leg_end,
            "records": [],
            "leg_atti_lists": {},   # cache: leg_num (str) → lista atti
            "done_keys": [],        # lista di "leg_num/atto_id" già processati
        }
        print(f"=== Ricognizione AkomaNtosoBulkData — Leg{args.leg_start} → Leg{args.leg_end} ===\n")

    # Costruiamo un set per lookup O(1)
    done_keys: set[str] = set(checkpoint.get("done_keys", []))
    all_records: list[dict] = list(checkpoint.get("records", []))

    print(f"Output CSV      : {args.out}")
    print(f"Checkpoint      : {cp_path}")
    print(f"Interrompi con  : Ctrl+C  (il progresso viene salvato dopo ogni atto)\n")

    try:
        for leg_num in range(args.leg_start, args.leg_end + 1):
            leg_name = f"Leg{leg_num}"
            leg_key = str(leg_num)

            # Recupera lista atti (dalla cache del checkpoint o da API)
            if leg_key in checkpoint.get("leg_atti_lists", {}):
                atti = checkpoint["leg_atti_lists"][leg_key]
                already_cached = True
            else:
                print(f"[{leg_name}] Recupero lista atti...", end=" ", flush=True)
                try:
                    atti = list_leg_atti(leg_name)
                except RuntimeError as e:
                    print(f"\n  ⚠️  Errore: {e} — salto {leg_name}")
                    continue

                if not atti:
                    print("nessun atto trovato (legislatura non presente o vuota).")
                    continue

                # Salva lista atti nel checkpoint
                checkpoint.setdefault("leg_atti_lists", {})[leg_key] = atti
                save_checkpoint(cp_path, checkpoint)
                already_cached = False

            # Conta quanti già fatti in questa leg
            done_in_leg = sum(1 for a in atti if f"{leg_num}/{a}" in done_keys)
            todo_in_leg = len(atti) - done_in_leg

            if not already_cached:
                print(f"trovati {len(atti)} atti.")

            if todo_in_leg == 0:
                print(f"[{leg_name}] Tutti gli atti già processati (da checkpoint) — salto.")
                # Stampa summary dai record già presenti
                leg_records = [r for r in all_records if r["legislatura"] == leg_num]
                print_leg_summary(leg_num, leg_records)
                continue

            if done_in_leg > 0:
                print(f"[{leg_name}] Riprendo: {done_in_leg}/{len(atti)} già fatti, resto {todo_in_leg}.")

            leg_records_new: list[dict] = []

            for i, atto_id in enumerate(atti, 1):
                key = f"{leg_num}/{atto_id}"

                if key in done_keys:
                    continue   # già processato in una sessione precedente

                print(
                    f"\r  [{leg_name}] {i}/{len(atti)} — {atto_id}        ",
                    end="", flush=True
                )

                try:
                    subdirs = list_atto_subdirs(leg_name, atto_id)
                except RuntimeError as e:
                    print(f"\n    ⚠️  Errore su {atto_id}: {e} — salto")
                    subdirs = set()

                record = build_record(leg_num, atto_id, subdirs)
                leg_records_new.append(record)
                all_records.append(record)
                done_keys.add(key)

                # Salva checkpoint dopo ogni atto
                checkpoint["records"] = all_records
                checkpoint["done_keys"] = list(done_keys)
                save_checkpoint(cp_path, checkpoint)

                time.sleep(API_DELAY)

            print()  # newline dopo la progress bar
            leg_records_all = [r for r in all_records if r["legislatura"] == leg_num]
            print_leg_summary(leg_num, leg_records_all)

    except KeyboardInterrupt:
        print("\n")
        if all_records:
            # Aggiorna e scrivi il checkpoint con i dati in memoria
            checkpoint["records"] = all_records
            checkpoint["done_keys"] = list(done_keys)
            save_checkpoint(cp_path, checkpoint)
            print(
                f"⚠️  Interruzione ricevuta (Ctrl+C).\n"
                f"   Progresso salvato: {len(all_records)} atti → {cp_path}\n"
                f"   Riavvia lo script per continuare da dove ti sei fermato."
            )
        else:
            print(
                f"⚠️  Interruzione ricevuta (Ctrl+C).\n"
                f"   Nessun dato ancora processato — al riavvio ripartirà dall'inizio."
            )
        return 1

    # --- Riepilogo globale ---
    print(f"\n{'='*50}")
    print("RIEPILOGO GLOBALE")
    print(f"{'='*50}")
    print(f"  Atti totali              : {len(all_records)}")
    processabili = sum(
        1 for r in all_records if r["has_ddlpres"] and (r["has_emend"] or r["has_emendc"])
    )
    print(f"  Processabili             : {processabili}  (ddlpres + emend/emendc)")
    print(f"\n  {'Leg':<8} {'Totale':>8} {'Process.':>10}")
    print(f"  {'─'*30}")
    for leg_num in range(args.leg_start, args.leg_end + 1):
        recs = [r for r in all_records if r["legislatura"] == leg_num]
        if not recs:
            continue
        proc = sum(1 for r in recs if r["has_ddlpres"] and (r["has_emend"] or r["has_emendc"]))
        print(f"  Leg{leg_num:<5} {len(recs):>8} {proc:>10}")

    # --- Scrivi CSV finale (merge con dati esistenti) ---
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "legislatura", "atto_id",
        "has_ddlcomm", "has_ddlmess", "has_ddlpres",
        "has_emend", "has_emendc",
        "has_resaula", "has_sommcomm",
    ]

    # Carica il CSV esistente per le legislature NON rielaborate in questa run,
    # così un --leg-start/end parziale non cancella le legislature già inventariate.
    legs_processed = set(range(args.leg_start, args.leg_end + 1))
    existing_rows: list[dict] = []
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    if int(row["legislatura"]) not in legs_processed:
                        existing_rows.append(row)
                except (KeyError, ValueError):
                    pass  # riga malformata, la scartiamo

    merged_records = existing_rows + all_records

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged_records)

    print(f"\n✅ Inventario salvato in: {out_path}")

    # Cancella il checkpoint (completamento avvenuto)
    clear_checkpoint(cp_path)
    print(f"   Checkpoint rimosso ({cp_path.name})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
