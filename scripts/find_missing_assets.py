#!/usr/bin/env python3
"""Inventory archive asset references that are missing from the local copy.

The local `Traut.com/` snapshot lost a handful of files that the live site still
serves -- most visibly the watercolour photo frames (`Watercolor_iweb_*.png`)
that iWeb's runtime composites around each thumbnail, so a local page renders
bare photos where traut.com renders framed ones.

This scans every reference the archive itself makes (HTML attributes, CSS
`url()`/`@import`, quoted paths in page JavaScript, RSS feed URLs), resolves it
against `Traut.com/`, and reports the ones with no local file. With `--live` it
also asks traut.com for each missing path and says which ones can be restored.

    python3 scripts/find_missing_assets.py            # local misses only
    python3 scripts/find_missing_assets.py --live     # + HTTP status on traut.com
    python3 scripts/find_missing_assets.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mirror_archive import STEM_TO_SLUG, TRAUT  # noqa: E402

LIVE_BASE = "https://traut.com/Traut.com/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# A reference that points at an archive asset rather than a page or a feed.
ASSET_RE = re.compile(r"^(?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)/")
ATTR_RE = re.compile(r"\b(src|href|background|poster|data)=([\"'])(.*?)\2", re.I | re.S)
CSS_URL_RE = re.compile(r"url\(\s*([\"']?)([^)\"']+)\1\s*\)", re.I)
CSS_IMPORT_RE = re.compile(r"@import\s+([\"'])([^\"']+)\1", re.I)
JS_STRING_RE = re.compile(r"([\"'])((?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)\\?/[^\"']*)\1")
FEED_RE = re.compile(r"\burl=\"((?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)/[^\"]*)\"")
XML_TAG_RE = re.compile(
    r"<(?:iphoto:thumbnail|iweb:micro)>((?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)/[^<]*)</"
)


def refs_in(path: Path) -> set[str]:
    """Every archive-asset path a file references, as written."""
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    found: set[str] = set()
    if suffix in (".html", ".htm"):
        found.update(m.group(3) for m in ATTR_RE.finditer(text))
        found.update(m.group(2) for m in CSS_URL_RE.finditer(text))
        found.update(m.group(2) for m in CSS_IMPORT_RE.finditer(text))
        found.update(m.group(2) for m in JS_STRING_RE.finditer(text))
    elif suffix == ".css":
        found.update(m.group(2) for m in CSS_URL_RE.finditer(text))
        found.update(m.group(2) for m in CSS_IMPORT_RE.finditer(text))
    elif suffix == ".js":
        found.update(m.group(2) for m in JS_STRING_RE.finditer(text))
    elif suffix == ".xml":
        found.update(m.group(1) for m in FEED_RE.finditer(text))
        found.update(m.group(1) for m in XML_TAG_RE.finditer(text))
    out = set()
    for ref in found:
        ref = unquote(ref.replace("\\/", "/")).strip()
        if not ref or ref.startswith(("http://", "https://", "data:", "mailto:", "#", "/")):
            continue
        if ref.startswith("./"):
            ref = ref[2:]
        if not ASSET_RE.match(ref):
            continue
        ref = ref.split("#")[0].split("?")[0]
        out.add(ref)
    return out


def referenced_files() -> list[Path]:
    """The archive files whose references matter (pages, their JS, CSS, feeds)."""
    files: list[Path] = []
    for stem in STEM_TO_SLUG:
        page = TRAUT / f"{stem}.html"
        if page.is_file():
            files.append(page)
        page_dir = TRAUT / f"{stem}_files"
        if page_dir.is_dir():
            files.extend(p for p in page_dir.iterdir() if p.suffix.lower() in (".js", ".css", ".xml"))
    files.extend(p for p in (TRAUT / "Scripts").rglob("*") if p.suffix.lower() in (".js", ".css"))
    files.extend(p for p in (TRAUT / "Media").glob("*.css"))
    return files


def local_path(ref: str) -> Path | None:
    """Where a reference should live. Refs are resolved from the site root."""
    candidate = TRAUT / ref
    if candidate.exists():
        return candidate
    return None


def live_status(ref: str, timeout: float = 20) -> tuple[int, int]:
    """(HTTP status, bytes) for the reference on traut.com."""
    url = urljoin(LIVE_BASE, ref)
    request = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, len(response.read())
    except Exception as error:  # noqa: BLE001 - report, do not crash
        status = getattr(error, "code", 0)
        return status, 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="ask traut.com for each miss")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not TRAUT.is_dir():
        print("missing Traut.com archive", file=sys.stderr)
        return 1

    missing: dict[str, list[str]] = {}
    for path in referenced_files():
        for ref in sorted(refs_in(path)):
            if local_path(ref) is None:
                missing.setdefault(ref, [])
                source = str(path.relative_to(TRAUT))
                if source not in missing[ref]:
                    missing[ref].append(source)

    report = []
    for ref in sorted(missing):
        entry = {"ref": ref, "referenced_by": missing[ref]}
        if args.live:
            status, size = live_status(ref)
            entry.update({"status": status, "bytes": size})
        report.append(entry)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"{len(report)} missing asset reference(s)")
    for entry in report:
        suffix = ""
        if args.live:
            suffix = f"  live={entry['status']} {entry['bytes']}B"
        print(f"  {entry['ref']}{suffix}")
        print(f"      <- {', '.join(entry['referenced_by'][:3])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
