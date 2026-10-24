#!/usr/bin/env python3
"""Mirror Traut.com into the Astro site, page for page.

Every route is the archive's own HTML driven by iWeb's own JavaScript, so the
photo grids, captions, slideshow, navbar, header/footer controls and canvas
shadows are produced by the original engine — nothing is re-implemented and
nothing can be missing.

The only edits are URL plumbing:

  * assets (`X_files/…`, `Media/…`, `Scripts/…`) -> `/archive/…`, served through
    the `public/archive` symlink; no asset is copied
  * page links (`Peru.html`) -> clean routes (`/peru`)
  * per-page JS and RSS feeds are written as rewritten copies under
    `public/page-js/` and `public/feeds/` so their relative URLs resolve too
  * the site navbar feed stays at `/feed.xml`, exactly like the original

One class of asset is the exception to "no asset is copied": the local archive
snapshot lost the eight watercolour photo-frame tiles that traut.com still
serves, so `restored/` (committed, with a manifest) holds them and those exact
paths are rewritten to `../restored/…`. See scripts/restore_assets.py.

`Traut.com/` is never modified.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
TRAUT = ROOT.parent / "Traut.com"
PUBLIC = ROOT / "public"
ARCHIVE_LINK = PUBLIC / "archive"

# Archive page stem -> clean route slug. "" is the landing page.
STEM_TO_SLUG = {
    "Welcome": "",
    "Antarctica_2011": "antarctica-2011",
    "Antarctic_Peninsula": "antarctic-peninsula",
    "Around_The_World": "around-the-world",
    "Australia": "australia",
    "Cambodia": "cambodia",
    "China": "china",
    "Easter_Island": "easter-island",
    "Egypt": "egypt",
    "Falkland_Islands": "falkland-islands",
    "Glacier_2010": "glacier-2010",
    "Iceland_2011": "iceland-2011",
    "India": "india",
    "Mediterranean_Cruise": "mediterranean-cruise",
    "Morocco": "morocco",
    "Northern_Namibia": "northern-namibia",
    "Okavango_Delta": "okavango-delta",
    "Patagonia": "patagonia",
    "Peru": "peru",
    "South_Georgia": "south-georgia",
    "Southern_Africa": "southern-africa",
    "Tanzania": "tanzania",
    "Tetons_2011": "tetons-2011",
    "Tibet": "tibet",
    "Utah_&_Arizona": "utah-arizona",
    "Washington_DC": "washington-dc",
    "Windhoek_and_Sossusvlei": "windhoek-and-sossusvlei",
    "Wrangell_Island_2013": "wrangell-island-2013",
    "Yellowstone_2013": "yellowstone-2013",
    "Yosemite_2010": "yosemite-2010",
    "Zambia_and_Chobe": "zambia-and-chobe",
}

# Extra archive filenames that must keep working (aliases on disk).
FILENAME_ALIASES = {"Utah_%26_Arizona": "utah-arizona"}

# Archive assets the local snapshot lost but traut.com still serves: a manifest
# of the exact archive paths, and the restored copy of each file. Rewriting only
# those paths keeps the overlay from shadowing anything the archive does have.
RESTORED_DIR = ROOT / "restored"
RESTORED_PREFIX = "../restored/"


def load_restored() -> dict[str, str]:
    """`{"Morocco_files/Watercolor_iweb_01.png": "../restored/Watercolor_iweb_01.png"}`"""
    manifest = RESTORED_DIR / "manifest.json"
    if not manifest.is_file():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        ref: RESTORED_PREFIX + name
        for name, meta in data.get("files", {}).items()
        for ref in meta.get("restores", [])
    }


RESTORED_REFS = load_restored()

# iWeb's String#toAbsoluteURL() prepends the document's directory to every URL
# that lacks ":/", so a root-absolute "/archive/…" would become
# "/peru//archive/…" and 404.  A relative "../archive/…" survives that: it
# resolves to "/archive/…" from any route ("/" clamps at the root).
ASSET_PREFIX = "../archive/"

ATTR_RE = re.compile(r"\b(src|href|background|poster|data)=([\"'])(.*?)\2", re.I | re.S)
IMPORT_RE = re.compile(r"(@import\s+)([\"'])([^\"']+)\2", re.I)
URL_FN_RE = re.compile(r"(url\(\s*)([\"']?)([^)\"']+)\2(\s*\))", re.I)
ASSET_PREFIX_RE = re.compile(r"^(?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)/")
# Quoted path literal inside inline JS: "Media/…", "Media\/…", 'X_files/…'.
JS_PATH_RE = re.compile(r"([\"'])((?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)\\?/)")
FEED_RE = re.compile(r"\.\./archive/[A-Za-z0-9_%&.\\/\-]*?rss\.xml")
# iWeb's NavBar fetches "<sitePath>/feed.xml"; the archive passed "." because it
# lived at the site root.  Our routes are one level down, so pass "..".
NAVBAR_SITE_PATH_RE = re.compile(
    r"(new\s+NavBar\(\s*'[^']*',\s*'[^']*',\s*'[^']*',\s*)'\.'"
)


def clean_route(stem: str) -> str:
    slug = STEM_TO_SLUG[stem]
    return "/" if slug == "" else f"/{slug}"


def page_key(stem: str) -> str:
    slug = STEM_TO_SLUG[stem]
    return "index" if slug == "" else slug


def rewrite_url(value: str) -> str:
    """One URL: page link -> clean route, archive asset -> ../archive/…"""
    raw = value.strip()
    if not raw or raw.startswith(
        ("http://", "https://", "mailto:", "javascript:", "data:", "#", "/", "//")
    ):
        return value
    path, sep, frag = raw.partition("#")
    if path.endswith(".html"):
        stem = unquote(path[: -len(".html")])
        if stem.startswith("./"):
            stem = stem[2:]
        if stem in STEM_TO_SLUG:
            return clean_route(stem) + (sep + frag if sep else "")
    if path in RESTORED_REFS:
        return RESTORED_REFS[path] + (sep + frag if sep else "")
    if ASSET_PREFIX_RE.match(path):
        return ASSET_PREFIX + path + (sep + frag if sep else "")
    return value


def rewrite_attrs(html: str) -> str:
    return ATTR_RE.sub(
        lambda m: f"{m.group(1)}={m.group(2)}{rewrite_url(m.group(3))}{m.group(2)}",
        html,
    )


def rewrite_css_refs(html: str) -> str:
    html = IMPORT_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{rewrite_url(m.group(3))}{m.group(2)}",
        html,
    )
    return URL_FN_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{rewrite_url(m.group(3))}{m.group(2)}{m.group(4)}",
        html,
    )


def rewrite_restored(text: str) -> str:
    r"""Quoted references to a restored asset -> ../restored/…

    Runs before the generic asset rewrite, so the paths that the archive lost
    never grow an `../archive/` prefix. iWeb escapes slashes in inline JS, so a
    reference may be written `X_files\/file.png`.
    """
    for ref, url in RESTORED_REFS.items():
        pattern = re.compile(
            r"([\"'])" + re.escape(ref).replace("/", r"\\?/") + r"([\"'])"
        )
        text = pattern.sub(lambda m: m.group(1) + url + m.group(2), text)
    return text


def rewrite_js_paths(text: str) -> str:
    """Quoted asset paths inside inline/page JavaScript -> ../archive/…"""
    return JS_PATH_RE.sub(lambda m: m.group(1) + ASSET_PREFIX + m.group(2), text)


def retarget_page_js(html: str, stem: str, key: str) -> str:
    """Load the rewritten copy of the page's own JS, not the archive original."""
    names = {
        f"{ASSET_PREFIX}{stem}_files/{stem}.js",
        f"{ASSET_PREFIX}{stem}_files/{stem.replace('&', '&amp;')}.js",
    }
    for name in names:
        if name in html:
            return html.replace(name, f"/page-js/{key}.js")
    # Utah's directory is reachable through its percent-encoded symlink.
    return re.sub(
        r"\.\./archive/[A-Za-z0-9_%&.\-]+_files/[A-Za-z0-9_%&.\-]+\.js(?=[\"'])",
        f"/page-js/{key}.js",
        html,
        count=1,
    )


def rewrite_page_html(html: str, stem: str, key: str) -> str:
    html = rewrite_restored(html)
    html = rewrite_attrs(html)
    html = rewrite_css_refs(html)
    html = rewrite_js_paths(html)
    html = retarget_page_js(html, stem, key)
    html = FEED_RE.sub(f"/feeds/{key}.xml", html)
    return NAVBAR_SITE_PATH_RE.sub(r"\1'..'", html)


def rewrite_page_js(js: str, key: str) -> str:
    js = rewrite_restored(js)
    js = rewrite_js_paths(js)
    return FEED_RE.sub(f"/feeds/{key}.xml", js)


def rewrite_feed(xml: str) -> str:
    """Relative asset URLs and clean page links inside a page's RSS feed."""
    xml = re.sub(
        r'\burl="((?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)/[^"]*)"',
        lambda m: 'url="' + ASSET_PREFIX + m.group(1) + '"',
        xml,
    )
    for tag in ("iphoto:thumbnail", "iweb:micro"):
        xml = re.sub(
            rf"(<{tag}>)((?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)/[^<]*)(</{tag}>)",
            lambda m: m.group(1) + ASSET_PREFIX + m.group(2) + m.group(3),
            xml,
        )

    def page_link(m: re.Match) -> str:
        path, frag = m.group(1), m.group(2) or ""
        stem = unquote(path[: -len(".html")])
        if stem.startswith("./"):
            stem = stem[2:]
        if stem not in STEM_TO_SLUG:
            return m.group(0)
        return f"<link>{clean_route(stem)}{frag}</link>"

    return re.sub(r"<link>([^<]*?\.html)(#[^<]*)?</link>", page_link, xml)


def ensure_archive_link() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_LINK.is_symlink() or ARCHIVE_LINK.exists():
        return
    ARCHIVE_LINK.symlink_to(Path("..") / ".." / "Traut.com")


def write_redirect_stubs() -> int:
    """Old iWeb filenames keep resolving to the clean routes."""
    mapping = {f"{stem}.html": clean_route(stem) for stem in STEM_TO_SLUG}
    mapping.pop("Welcome.html")  # served as the landing page itself
    mapping.update({f"{name}.html": f"/{slug}" for name, slug in FILENAME_ALIASES.items()})
    for name, href in mapping.items():
        (PUBLIC / name).write_text(
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\"/>"
            f'<meta http-equiv="refresh" content="0;url={href}"/>'
            f'<link rel="canonical" href="{href}"/>'
            f"<script>location.replace({href!r})</script>"
            f'</head><body><a href="{href}">{href}</a></body></html>\n',
            encoding="utf-8",
        )
    return len(mapping)


def publish_site_feed() -> None:
    """The navbar asks the site root for feed.xml, as it did on traut.com."""
    src = TRAUT / "feed.xml"
    if src.is_file():
        shutil.copyfile(src, PUBLIC / "feed.xml")


def write_page_assets() -> int:
    """Rewrite each page's own script and photo feed under public/."""
    count = 0
    page_js = PUBLIC / "page-js"
    feeds = PUBLIC / "feeds"
    for d in (page_js, feeds):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    for stem, slug in STEM_TO_SLUG.items():
        key = page_key(stem)
        src = TRAUT / f"{stem}.html"
        if not src.is_file():
            raise SystemExit(f"missing archive page {src}")
        count += 1
        js_src = TRAUT / f"{stem}_files" / f"{stem}.js"
        if js_src.is_file():
            (page_js / f"{key}.js").write_text(
                rewrite_page_js(js_src.read_text(encoding="utf-8", errors="replace"), key),
                encoding="utf-8",
            )
        rss_src = TRAUT / f"{stem}_files" / "rss.xml"
        if rss_src.is_file():
            (feeds / f"{key}.xml").write_text(
                rewrite_feed(rss_src.read_text(encoding="utf-8", errors="replace")),
                encoding="utf-8",
            )
    return count


def publish_restored() -> int:
    """Copy the restored overlay into public/restored/ (a few KB, every build)."""
    if not RESTORED_REFS:
        return 0
    target = PUBLIC / "restored"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    count = 0
    for url in sorted(set(RESTORED_REFS.values())):
        name = url[len(RESTORED_PREFIX) :]
        shutil.copyfile(RESTORED_DIR / name, target / name)
        count += 1
    return count


def publish_welcome_alias() -> None:
    """Keep the archive's filename working: /Welcome.html serves the landing page."""
    dist = ROOT / "dist"
    index = dist / "index.html"
    if not index.is_file():
        return
    html = index.read_text(encoding="utf-8")
    if 'id="body_layer"' not in html:
        return
    (dist / "Welcome.html").write_text(html, encoding="utf-8")


def relink_dist_archive() -> None:
    """Astro copies public/archive by value (285MB). Put a symlink back."""
    dist = ROOT / "dist"
    if not dist.is_dir():
        return
    dist_arch = dist / "archive"
    target = Path("..") / ".." / "Traut.com"
    if dist_arch.is_symlink():
        return
    if dist_arch.exists():
        shutil.rmtree(dist_arch)
    dist_arch.symlink_to(target)


def main() -> int:
    if not TRAUT.is_dir():
        print("missing Traut.com archive", file=sys.stderr)
        return 1
    ensure_archive_link()
    restored = publish_restored()
    pages = write_page_assets()
    stubs = write_redirect_stubs()
    publish_site_feed()
    print(
        f"mirror_archive: {pages} pages, "
        f"{len(list((PUBLIC / 'page-js').glob('*.js')))} page scripts, "
        f"{len(list((PUBLIC / 'feeds').glob('*.xml')))} feeds, "
        f"{restored} restored assets, "
        f"{stubs} redirect stubs -> {PUBLIC}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
