#!/usr/bin/env python
"""
Pilot extractor for Senato AkomaNtosoBulkData.

Usage examples:
  uv run script/senato_pilot.py list-atti --limit 10
  uv run script/senato_pilot.py inspect-atto Atto00055177
  uv run script/senato_pilot.py read-file Leg19/Atto00055177/README.MD
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


OWNER = "SenatoDellaRepubblica"
REPO = "AkomaNtosoBulkData"
REF = "master"
API_ROOT = f"https://api.github.com/repos/{OWNER}/{REPO}"
GH_AVAILABLE = shutil.which("gh") is not None
INTERESTING_DIRS = {
    "ddlpres",
    "ddlcomm",
    "ddlmess",
    "emend",
    "emendc",
    "resaula",
    "sommcomm",
}


class GitHubApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContentItem:
    name: str
    path: str
    type: str
    size: int | None
    download_url: str | None

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "ContentItem":
        return cls(
            name=item["name"],
            path=item["path"],
            type=item["type"],
            size=item.get("size"),
            download_url=item.get("download_url"),
        )


def github_get(path: str, *, accept: str = "application/vnd.github+json") -> Any:
    if GH_AVAILABLE:
        return github_get_with_gh(path, accept=accept)

    req = urllib.request.Request(
        f"{API_ROOT}/{path}",
        headers={
            "Accept": accept,
            "User-Agent": "iter-legis-senato-pilot",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            content_type = resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GitHubApiError(f"GitHub API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GitHubApiError(f"GitHub API request failed: {exc}") from exc

    if "application/json" in content_type:
        return json.loads(body.decode("utf-8"))
    return body.decode("utf-8", errors="replace")


def github_get_with_gh(path: str, *, accept: str) -> Any:
    endpoint = f"repos/{OWNER}/{REPO}/{path}"
    cmd = ["gh", "api", endpoint, "--header", f"Accept: {accept}"]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubApiError(f"gh api request failed: {exc}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise GitHubApiError(f"gh api failed for {endpoint}: {detail}")

    if accept == "application/vnd.github.raw":
        return proc.stdout
    return json.loads(proc.stdout)


def contents(path: str) -> list[ContentItem]:
    quoted = urllib.parse.quote(path.strip("/"))
    data = github_get(f"contents/{quoted}?ref={REF}")
    if not isinstance(data, list):
        raise GitHubApiError(f"Expected directory listing for {path}, got file metadata")
    return [ContentItem.from_api(item) for item in data]


def read_text_file(path: str) -> str:
    quoted = urllib.parse.quote(path.strip("/"))
    if GH_AVAILABLE:
        return github_get(f"contents/{quoted}?ref={REF}", accept="application/vnd.github.raw")

    data = github_get(f"contents/{quoted}?ref={REF}")
    if isinstance(data, str):
        return data
    if data.get("encoding") != "base64":
        raise GitHubApiError(f"Unsupported file encoding for {path}: {data.get('encoding')}")
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def emit_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_list_atti(args: argparse.Namespace) -> None:
    rows = []
    for item in contents(f"Leg{args.legislatura}"):
        if item.type == "dir" and item.name.startswith("Atto"):
            rows.append({"atto": item.name, "path": item.path})
        if len(rows) >= args.limit:
            break
    emit_json(rows)


def command_inspect_atto(args: argparse.Namespace) -> None:
    atto_path = f"Leg{args.legislatura}/{args.atto}"
    items = contents(atto_path)
    emit_json(
        {
            "atto": args.atto,
            "path": atto_path,
            "items": [
                {
                    "name": item.name,
                    "type": item.type,
                    "path": item.path,
                    "size": item.size,
                    "download_url": item.download_url,
                }
                for item in items
            ],
        }
    )


def command_list_dir(args: argparse.Namespace) -> None:
    emit_json(
        [
            {
                "name": item.name,
                "type": item.type,
                "path": item.path,
                "size": item.size,
                "download_url": item.download_url,
            }
            for item in contents(args.path)
        ]
    )


def command_find_rich_atti(args: argparse.Namespace) -> None:
    if args.scan:
        command_scan_rich_atti(args)
        return

    data = github_get(f"git/trees/{REF}?recursive=1")
    rows_by_atto: dict[str, dict[str, Any]] = {}

    for item in data.get("tree", []):
        path = item.get("path", "")
        parts = path.split("/")
        if len(parts) < 3:
            continue
        leg, atto, child = parts[:3]
        if leg != f"Leg{args.legislatura}" or not atto.startswith("Atto"):
            continue

        row = rows_by_atto.setdefault(
            atto,
            {
                "atto": atto,
                "path": f"{leg}/{atto}",
                "interesting_dirs": set(),
                "xml_files": 0,
                "readme": False,
            },
        )
        if child in INTERESTING_DIRS:
            row["interesting_dirs"].add(child)
        if path.endswith(".akn.xml"):
            row["xml_files"] += 1
        if child.upper() == "README.MD":
            row["readme"] = True

    rows = []
    for row in rows_by_atto.values():
        interesting_dirs = sorted(row["interesting_dirs"])
        if len(interesting_dirs) < args.min_dirs:
            continue
        rows.append(
            {
                "atto": row["atto"],
                "path": row["path"],
                "interesting_dirs": interesting_dirs,
                "xml_files": row["xml_files"],
                "readme": row["readme"],
            }
        )

    rows.sort(key=lambda item: (len(item["interesting_dirs"]), item["xml_files"]), reverse=True)
    emit_json(
        {
            "truncated": data.get("truncated", False),
            "count": len(rows),
            "results": rows[: args.limit],
        }
    )


def command_scan_rich_atti(args: argparse.Namespace) -> None:
    candidates = []
    checked = 0

    for item in contents(f"Leg{args.legislatura}"):
        if item.type != "dir" or not item.name.startswith("Atto"):
            continue
        if checked >= args.scan:
            break
        checked += 1

        try:
            children = contents(item.path)
        except GitHubApiError as exc:
            candidates.append({"atto": item.name, "path": item.path, "error": str(exc)})
            continue

        interesting = sorted(child.name for child in children if child.name in INTERESTING_DIRS)
        if len(interesting) >= args.min_dirs:
            candidates.append(
                {
                    "atto": item.name,
                    "path": item.path,
                    "interesting_dirs": interesting,
                    "top_level_items": [child.name for child in children],
                }
            )
        if len(candidates) >= args.limit:
            break

    emit_json({"checked": checked, "count": len(candidates), "results": candidates})


def command_read_file(args: argparse.Namespace) -> None:
    print(read_text_file(args.path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stepwise Senato bulk-data pilot")
    sub = parser.add_subparsers(dest="command", required=True)

    list_atti = sub.add_parser("list-atti", help="List Atto directories for a legislature")
    list_atti.add_argument("--legislatura", default="19")
    list_atti.add_argument("--limit", type=int, default=20)
    list_atti.set_defaults(func=command_list_atti)

    inspect = sub.add_parser("inspect-atto", help="Inspect top-level files for one Atto")
    inspect.add_argument("atto", help="Example: Atto00055177")
    inspect.add_argument("--legislatura", default="19")
    inspect.set_defaults(func=command_inspect_atto)

    list_dir = sub.add_parser("list-dir", help="List any repository directory")
    list_dir.add_argument("path", help="Example: Leg19/Atto00055177/ddlpres")
    list_dir.set_defaults(func=command_list_dir)

    rich = sub.add_parser("find-rich-atti", help="Find Atto directories with useful output types")
    rich.add_argument("--legislatura", default="19")
    rich.add_argument("--limit", type=int, default=20)
    rich.add_argument("--min-dirs", type=int, default=2)
    rich.add_argument("--scan", type=int, default=0, help="Scan first N Atto folders one by one")
    rich.set_defaults(func=command_find_rich_atti)

    read_file = sub.add_parser("read-file", help="Print a repository text file")
    read_file.add_argument("path", help="Example: Leg19/Atto00055177/README.MD")
    read_file.set_defaults(func=command_read_file)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except GitHubApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
