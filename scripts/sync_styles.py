#!/usr/bin/env python3
"""Bring the archive's stylesheets into the project.

iWeb generated one stylesheet per page (`Peru_files/Peru.css`) plus three shared
widget stylesheets (`Scripts/Widgets/*/*.css`). Those files are the site's real
typography and layout, so the port imports them through Astro's CSS pipeline
instead of linking out of `Traut.com/`.

The copies are byte-for-byte the archive's (after a one-line provenance
header), which keeps the cascade identical and lets `npm test` prove it.

    python3 scripts/sync_styles.py           # write src/styles/**
    python3 scripts/sync_styles.py --check   # fail if a copy drifted
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mirror_archive import STEM_TO_SLUG, TRAUT, page_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STYLES = ROOT / "src" / "styles"

# iWeb widget stylesheet -> project filename.
WIDGETS = {
    "headerControls": "Scripts/Widgets/HeaderControls/HeaderControls.css",
    "detailView": "Scripts/Widgets/DetailView/DetailView.css",
    "footerControls": "Scripts/Widgets/FooterControls/FooterControls.css",
}


def header(source: str) -> str:
    return f"/* Copied from Traut.com/{source} by scripts/sync_styles.py -- do not edit. */\n"


def wanted() -> dict[Path, tuple[str, str]]:
    """project path -> (archive source, css text)"""
    out: dict[Path, tuple[str, str]] = {}
    for stem in STEM_TO_SLUG:
        source = f"{stem}_files/{stem}.css"
        path = STYLES / "pages" / f"{page_key(stem)}.css"
        out[path] = (source, (TRAUT / source).read_text(encoding="utf-8", errors="replace"))
    for name, source in WIDGETS.items():
        out[STYLES / "widgets" / f"{kebab(name)}.css"] = (
            source,
            (TRAUT / source).read_text(encoding="utf-8", errors="replace"),
        )
    return out


def kebab(name: str) -> str:
    return "".join("-" + c.lower() if c.isupper() else c for c in name).lstrip("-")


def body_of(path: Path) -> str:
    """The copy without its provenance header."""
    text = path.read_text(encoding="utf-8")
    return text.split("\n", 1)[1] if text.startswith("/* Copied from") else text


def main(argv: list[str]) -> int:
    if not TRAUT.is_dir():
        print("missing Traut.com archive", file=sys.stderr)
        return 1
    check = "--check" in argv
    files = wanted()
    stale: list[str] = []
    for path, (source, css) in files.items():
        expected = header(source) + css
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != expected:
                stale.append(str(path.relative_to(ROOT)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
    if check:
        if stale:
            print("styles out of date (run scripts/sync_styles.py): " + ", ".join(stale[:5]))
            return 1
        print(f"ok styles: {len(files)} stylesheets match the archive")
        return 0
    # Remove copies of pages that no longer exist.
    for path in (STYLES / "pages").glob("*.css"):
        if path not in files:
            path.unlink()
    print(f"sync_styles: {len(files)} stylesheets -> {STYLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
