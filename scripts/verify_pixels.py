#!/usr/bin/env python3
"""Pixel-compare every mirrored route with the archive page it came from.

Serves `Traut.com/` and `dist/` on two local ports, screenshots each pair in
headless Chromium and reports the diff bounding box.  A page that is truthful
reports `bbox=None` (no differing pixel).

    python3 scripts/verify_pixels.py            # all 31 pages
    python3 scripts/verify_pixels.py peru tibet # just these routes

Chromium is looked up in $CHROME, then in the usual Playwright cache; pass
`--chrome /path/to/chrome` to override.  Needs Pillow.
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import time
from pathlib import Path
from shutil import which

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mirror_archive import STEM_TO_SLUG, TRAUT  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
OUT = Path("/tmp/traut-pixels")
SIZE = (800, 1400)
BUDGET = "8000"


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    hits = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium*/chrome-linux*/chrome")))
    hits += sorted(
        glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
    )
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = which(name)
        if found:
            hits.append(found)
    if not hits:
        raise SystemExit("no Chromium found; pass --chrome /path/to/chrome")
    return hits[-1]


def shot(chrome: str, url: str, dest: Path) -> None:
    subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--virtual-time-budget={BUDGET}",
            f"--window-size={SIZE[0]},{SIZE[1]}",
            f"--screenshot={dest}",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("routes", nargs="*", help="slugs to check (default: all)")
    ap.add_argument("--chrome", default=None)
    args = ap.parse_args()

    chrome = find_chrome(args.chrome)
    if not DIST.is_dir():
        raise SystemExit("run `npm run build` first")
    OUT.mkdir(parents=True, exist_ok=True)

    pairs = [
        (stem, slug)
        for stem, slug in sorted(STEM_TO_SLUG.items())
        if not args.routes or (slug or "index") in args.routes or stem in args.routes
    ]
    servers = [
        subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port)],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for port, cwd in ((8231, TRAUT), (8232, DIST))
    ]
    time.sleep(1.5)

    differing: list[str] = []
    try:
        for stem, slug in pairs:
            name = slug or "index"
            archive_png = OUT / f"archive_{name}.png"
            mirror_png = OUT / f"mirror_{name}.png"
            shot(chrome, f"http://127.0.0.1:8231/{stem}.html", archive_png)
            shot(chrome, f"http://127.0.0.1:8232{'/' if not slug else '/' + slug + '/'}", mirror_png)
            a = Image.open(archive_png).convert("RGB")
            b = Image.open(mirror_png).convert("RGB")
            if a.size != b.size:
                print(f"{name:24s} SIZE {a.size} != {b.size}")
                differing.append(name)
                continue
            diff = ImageChops.difference(a, b)
            bbox = diff.getbbox()
            mean = [round(v, 3) for v in ImageStat.Stat(diff).mean]
            if bbox is not None:
                differing.append(name)
            print(f"{name:24s} {'DIFF' if bbox else 'ok':4s} bbox={bbox} mean={mean}")
    finally:
        for proc in servers:
            proc.terminate()

    print()
    print(f"identical: {len(pairs) - len(differing)}/{len(pairs)}")
    if differing:
        print("differing:", ", ".join(differing))
    return 1 if differing else 0


if __name__ == "__main__":
    raise SystemExit(main())
