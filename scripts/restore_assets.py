#!/usr/bin/env python3
"""Restore archive assets the local snapshot lost but traut.com still serves.

The `Traut.com/` copy this port was built from is incomplete: it is missing the
eight `Watercolor_iweb_*.png` tiles that iWeb's runtime composites into every
`.framedImage` photo frame, so a local page renders bare photos where the live
site renders framed ones. (The summary that came with the copy claimed those
files 404 upstream; they do not.)

`restored/` holds those files, committed, with a manifest of the exact archive
paths each one stands in for. `scripts/mirror_archive.py` rewrites only those
paths to `../restored/…`, and the verification tools serve the same overlay when
they render the archive side, so the local oracle is "the archive as traut.com
serves it".

    python3 scripts/restore_assets.py            # print the manifest
    python3 scripts/restore_assets.py --fetch    # (re)download what is missing
    python3 scripts/restore_assets.py --check    # verify files + coverage

`Traut.com/` is never written to.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_missing_assets import LIVE_BASE, UA, local_path, referenced_files, refs_in  # noqa: E402
from mirror_archive import TRAUT  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESTORED = ROOT / "restored"
MANIFEST = RESTORED / "manifest.json"


def missing_refs() -> dict[str, list[str]]:
    """Archive asset refs with no local file, and who references them."""
    missing: dict[str, list[str]] = {}
    for path in referenced_files():
        for ref in sorted(refs_in(path)):
            if local_path(ref) is not None:
                continue
            source = str(path.relative_to(TRAUT))
            missing.setdefault(ref, [])
            if source not in missing[ref]:
                missing[ref].append(source)
    return missing


def download(ref: str) -> bytes | None:
    url = LIVE_BASE + ref
    try:
        with urlopen(Request(url, headers={"User-Agent": UA}), timeout=30) as response:
            return response.read()
    except Exception as error:  # noqa: BLE001 - report, do not crash
        print(f"  !! {ref}: {error}", file=sys.stderr)
        return None


def fetch() -> int:
    """Download every missing ref, one file per distinct content."""
    missing = missing_refs()
    if not missing:
        print("nothing missing: the local archive has every asset it references")
        return 0

    RESTORED.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict] = {}
    by_hash: dict[str, str] = {}
    for ref in sorted(missing):
        data = download(ref)
        if data is None:
            continue
        digest = hashlib.sha256(data).hexdigest()
        name = by_hash.get(digest)
        if name is None:
            name = Path(ref).name
            stem, suffix = Path(name).stem, Path(name).suffix
            if (RESTORED / name).exists() and hashlib.sha256((RESTORED / name).read_bytes()).hexdigest() != digest:
                name = f"{stem}-{digest[:8]}{suffix}"
            (RESTORED / name).write_bytes(data)
            by_hash[digest] = name
            files[name] = {
                "sha256": digest,
                "bytes": len(data),
                "restores": [],
            }
        files[name]["restores"].append(ref)

    for name in files:
        files[name]["restores"].sort()
    MANIFEST.write_text(
        json.dumps(
            {
                "source": LIVE_BASE,
                "note": (
                    "Archive assets the local Traut.com snapshot is missing. "
                    "traut.com still serves them; mirror_archive.py rewrites "
                    "these exact paths to ../restored/<file>."
                ),
                "files": dict(sorted(files.items())),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"restored: {len(files)} file(s) covering {sum(len(f['restores']) for f in files.values())} refs -> {RESTORED}")
    return 0


def check() -> int:
    """The committed overlay is intact and still exactly covers what is missing."""
    if not MANIFEST.is_file():
        print(f"missing {MANIFEST}; run --fetch", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    problems: list[str] = []
    covered: set[str] = set()

    for name, meta in files.items():
        path = RESTORED / name
        if not path.is_file():
            problems.append(f"{name}: missing from restored/")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            problems.append(f"{name}: sha256 differs from the manifest")
        if len(data) != meta["bytes"]:
            problems.append(f"{name}: {len(data)} bytes, manifest says {meta['bytes']}")
        for ref in meta["restores"]:
            covered.add(ref)
            if (TRAUT / ref).exists():
                problems.append(f"{name}: {ref} exists in Traut.com now; the overlay is stale")

    unmanaged = sorted(set(missing_refs()) - covered)
    if unmanaged:
        problems.append(f"{len(unmanaged)} missing ref(s) not in the overlay, e.g. {unmanaged[:3]}")

    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"ok restored: {len(files)} files cover {len(covered)} missing archive refs")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="download missing assets from traut.com")
    parser.add_argument("--check", action="store_true", help="verify the committed overlay")
    args = parser.parse_args()

    if not TRAUT.is_dir():
        print("missing Traut.com archive", file=sys.stderr)
        return 1
    if args.fetch:
        return fetch()
    if args.check:
        return check()

    if MANIFEST.is_file():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for name, meta in manifest["files"].items():
            print(f"{name}  {meta['bytes']}B  restores {len(meta['restores'])} ref(s)")
        return 0
    print("no restored/ manifest yet; run --fetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
