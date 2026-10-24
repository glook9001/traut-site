#!/usr/bin/env python3
"""Pixel-compare every mirrored route with the archive page it came from.

Serves `Traut.com/` and `dist/` on two local ports, screenshots each pair in
headless Chromium and reports the diff bounding box.  A page that is truthful
reports `bbox=None` (no differing pixel).

The archive side is served with the `restored/` overlay on top (the eight
watercolour photo-frame tiles the local copy lost, which traut.com still
serves), so it renders what the live site renders. `--live` compares against
https://traut.com itself instead.

    python3 scripts/verify_pixels.py            # all 31 pages
    python3 scripts/verify_pixels.py peru tibet # just these routes
    python3 scripts/verify_pixels.py --live     # oracle = traut.com

The screenshots are **full page** (scripts/shot.mjs clips to the document's real
content size), not viewport-sized: an album page is ~2900 px tall, and comparing
only the top 1400 px would miss most of the photo grid.

Chromium is looked up in $CHROME, then in the usual Playwright cache; pass
`--chrome /path/to/chrome` to override.  Needs Pillow.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from shutil import which

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mirror_archive import RESTORED_DIR, STEM_TO_SLUG, TRAUT  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
OUT = Path("/tmp/traut-pixels")
# How long to let iWeb's scripts lay the page out before the shot. The live
# site also has to fetch its photos over the network.
BUDGET = "3000"
BUDGET_LIVE = "8000"
SHOT = ROOT / "scripts" / "shot.mjs"
LIVE = "https://traut.com/Traut.com/"


def restored_overlay() -> dict[str, Path]:
    """`{"Morocco_files/Watercolor_iweb_01.png": restored/Watercolor_iweb_01.png}`"""
    manifest = RESTORED_DIR / "manifest.json"
    if not manifest.is_file():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        ref: RESTORED_DIR / name
        for name, meta in data.get("files", {}).items()
        for ref in meta.get("restores", [])
    }


class OverlayHandler(SimpleHTTPRequestHandler):
    """The archive as traut.com serves it: local files, restored ones on a miss."""

    def translate_path(self, path):  # noqa: D102
        local = super().translate_path(path)
        if os.path.exists(local):
            return local
        ref = os.path.relpath(local, TRAUT).replace(os.sep, "/")
        overlay = self.server.overlay  # type: ignore[attr-defined]
        return str(overlay.get(ref, local))

    def log_message(self, *args):  # noqa: D102
        pass


def find_chrome(explicit: str | None) -> str | None:
    """Only used for the error message; scripts/shot.mjs does the real lookup."""
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
    return hits[-1] if hits else None


def shot(url: str, dest: Path, budget: str = BUDGET, timeout: float = 150) -> bool:
    """Full-page screenshot through the DevTools protocol (see shot.mjs).

    A hung Chromium used to hang the whole run; `shot.mjs` has its own watchdog,
    and this is the outer one. A failed shot leaves no file, which the caller
    reports as a failed page rather than crashing on `Image.open`.
    """
    dest.unlink(missing_ok=True)
    try:
        subprocess.run(
            ["node", str(SHOT), url, str(dest), budget],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"  shot timed out after {timeout:g}s: {url}", flush=True)
        dest.unlink(missing_ok=True)
    return dest.is_file()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("routes", nargs="*", help="slugs to check (default: all)")
    ap.add_argument("--chrome", default=None)
    ap.add_argument("--live", action="store_true", help="use traut.com as the oracle")
    args = ap.parse_args()

    if args.chrome:
        os.environ["CHROME"] = args.chrome
    if not find_chrome(args.chrome):
        raise SystemExit("no Chromium found; pass --chrome /path/to/chrome")
    if not DIST.is_dir():
        raise SystemExit("run `npm run build` first")
    OUT.mkdir(parents=True, exist_ok=True)

    pairs = [
        (stem, slug)
        for stem, slug in sorted(STEM_TO_SLUG.items())
        if not args.routes or (slug or "index") in args.routes or stem in args.routes
    ]
    archive_server = None
    if not args.live:
        archive_server = ThreadingHTTPServer(("127.0.0.1", 8231), partial(OverlayHandler, directory=str(TRAUT)))
        archive_server.overlay = restored_overlay()  # type: ignore[attr-defined]
        threading.Thread(target=archive_server.serve_forever, daemon=True).start()
    dist_server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8232"],
        cwd=DIST,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)

    differing: list[str] = []
    print(f"comparing {len(pairs)} page(s), full page", flush=True)
    try:
        for stem, slug in pairs:
            name = slug or "index"
            archive_png = OUT / f"archive_{name}.png"
            mirror_png = OUT / f"mirror_{name}.png"
            if args.live:
                ok = shot(LIVE + f"{stem}.html", archive_png, BUDGET_LIVE, 240)
            else:
                ok = shot(f"http://127.0.0.1:8231/{stem}.html", archive_png)
            ok = shot(f"http://127.0.0.1:8232{'/' if not slug else '/' + slug + '/'}", mirror_png) and ok
            if not ok:
                differing.append(name)
                print(f"{name:24s} FAIL could not screenshot the page", flush=True)
                continue
            a = Image.open(archive_png).convert("RGB")
            b = Image.open(mirror_png).convert("RGB")
            if a.size != b.size:
                print(f"{name:24s} SIZE {a.size} != {b.size}", flush=True)
                differing.append(name)
                continue
            diff = ImageChops.difference(a, b)
            bbox = diff.getbbox()
            mean = [round(v, 3) for v in ImageStat.Stat(diff).mean]
            if bbox is not None:
                differing.append(name)
            print(f"{name:24s} {'DIFF' if bbox else 'ok':4s} bbox={bbox} mean={mean}", flush=True)
    finally:
        dist_server.terminate()
        if archive_server is not None:
            archive_server.shutdown()
            archive_server.server_close()

    print()
    print(f"identical: {len(pairs) - len(differing)}/{len(pairs)}")
    if differing:
        print("differing:", ", ".join(differing))
    return 1 if differing else 0


if __name__ == "__main__":
    raise SystemExit(main())
