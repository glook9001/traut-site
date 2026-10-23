#!/usr/bin/env python3
"""Verify the port: every archive page is rebuilt by Astro, unchanged.

The pages in `src/pages/` are real Astro components fed by the data models that
`scripts/extract_pages.py` derives from `Traut.com/`.  So the contract is no
longer "byte-equal to the archive" (Astro rewrites the doctype, self-closing
tags and inter-element whitespace); it is:

  * the DOM is the archive's DOM -- same elements, attributes, classes, ids and
    text, only the URL plumbing rewritten (see mirror_archive.rewrite_page_html,
    which stays the oracle);
  * every visible word is the archive's own;
  * every asset, page script and feed resolves, and the ones the archive is
    missing stay missing;
  * the XHTML doctype survives, because it puts the browser in almost standards
    mode and that changes the layout by a few pixels (see iweb-doctype.mjs);
  * `Traut.com/` was never touched.

Run `npm run build` first.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mirror_archive import (  # noqa: E402
    ASSET_PREFIX,
    FILENAME_ALIASES,
    STEM_TO_SLUG,
    TRAUT,
    clean_route,
    page_key,
    rewrite_page_html,
    rewrite_page_js,
)

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
MODELS = ROOT / "src" / "data" / "pages"

# Assets the archive itself is missing (its <img> tags 404 on traut.com too).
# They must stay missing -- we never invent files the original never had.
KNOWN_MISSING = {"Watercolor_iweb_", "Media/transparent.gif"}

XHTML_DOCTYPE = (
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
    '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
)

VOID = {
    "br",
    "img",
    "meta",
    "link",
    "input",
    "hr",
    "area",
    "base",
    "col",
    "param",
    "source",
}
ATTR_RE = re.compile(r"\b(?:src|href|background|poster|data)=([\"'])(.*?)\1", re.I | re.S)


def fail(msg: str) -> None:
    raise AssertionError(msg)


def dist_page(slug: str) -> Path:
    return DIST / "index.html" if slug == "" else DIST / slug / "index.html"


def archive_html(stem: str) -> str:
    return (TRAUT / f"{stem}.html").read_text(encoding="utf-8", errors="replace")


class TextExtractor(HTMLParser):
    """Visible text only: skip <script>/<style> bodies."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):  # noqa: D102
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):  # noqa: D102
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):  # noqa: D102
        if not self._skip:
            self.chunks.append(data)


def visible_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.chunks)).strip()


class Skeleton(HTMLParser):
    """A comparable DOM: elements + attributes + meaningful text.

    Whitespace-only text nodes and Astro's own `data-astro-*` attributes are
    dropped, because `compressHTML` and scoped styles add or remove exactly
    those and nothing else.  Everything else has to match the archive.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: list = []
        self.stack: list[list] = [self.root]

    def handle_starttag(self, tag, attrs):  # noqa: D102
        node = [tag, self._attrs(attrs), []]
        self.stack[-1].append(node)
        if tag not in VOID:
            self.stack.append(node[2])

    def handle_startendtag(self, tag, attrs):  # noqa: D102
        self.stack[-1].append([tag, self._attrs(attrs), []])

    def handle_endtag(self, tag):  # noqa: D102
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i - 1][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):  # noqa: D102
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.stack[-1].append(["#text", {}, text])

    def handle_comment(self, data):  # noqa: D102
        if data.strip():
            self.stack[-1].append(["#comment", {}, data.strip()])

    @staticmethod
    def _attrs(attrs) -> dict[str, str]:
        return {
            name: (value if value is not None else "")
            for name, value in attrs
            if not name.startswith("data-astro-")
        }


def skeleton(html: str) -> list:
    parser = Skeleton()
    parser.feed(html)
    return parser.root


def first_difference(a, b, path="") -> str | None:
    """Where two skeletons diverge, as a readable path."""
    if type(a) is not type(b):
        return f"{path}: {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} children != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            diff = first_difference(x, y, f"{path}/{i}")
            if diff:
                return diff
        return None
    if isinstance(a, dict):
        if a != b:
            return f"{path}: attrs {a} != {b}"
        return None
    if a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def archive_refs(html: str) -> list[str]:
    """Relative archive-relative asset paths referenced by a page."""
    out = []
    for m in ATTR_RE.finditer(html):
        value = m.group(2).strip()
        if not value or value.startswith(("http", "mailto:", "javascript:", "data:", "#", "/")):
            continue
        path = value.split("#")[0]
        if path.endswith(".html"):
            continue
        out.append(path)
    return out


def mirror_refs(html: str) -> list[str]:
    return [m.group(2) for m in ATTR_RE.finditer(html) if m.group(2).startswith(ASSET_PREFIX)]


def on_disk(ref: str) -> bool:
    path = unquote(ref.split("?")[0])
    if path.startswith(ASSET_PREFIX):
        path = path[len(ASSET_PREFIX) :]
    return (TRAUT / path).is_file()


JS_REF_RE = re.compile(
    r"[\"']((?:\.\./archive/)?(?:Media|Scripts|[A-Za-z0-9_%&.\-]+_files)/[^\"']*)[\"']"
)


def js_refs(text: str) -> list[str]:
    return JS_REF_RE.findall(text)


# ---------------------------------------------------------------------------


def test_page_models() -> None:
    """Every archive page has a model, and the Astro route reads it."""
    models = {p.stem for p in MODELS.glob("*.json")}
    expected = {page_key(stem) for stem in STEM_TO_SLUG}
    if models != expected:
        fail(f"page models differ: missing {sorted(expected - models)}, extra {sorted(models - expected)}")
    for stem in STEM_TO_SLUG:
        model = json.loads((MODELS / f"{page_key(stem)}.json").read_text(encoding="utf-8"))
        if model["stem"] != stem or model["key"] != page_key(stem):
            fail(f"{page_key(stem)}.json is not the model for {stem}.html")
        if not model["head"]["items"] or not model["body"]["body"]["items"]:
            fail(f"{page_key(stem)}.json is empty")
    print(f"ok models: {len(models)} page models")


def test_dist_routes() -> None:
    if not DIST.is_dir():
        fail("run `npm run build` first")
    missing = [slug for slug in STEM_TO_SLUG.values() if not dist_page(slug).is_file()]
    if missing:
        fail(f"routes without a page: {missing}")
    routes = sorted(p for p in DIST.glob("*/index.html") if p.parent.name != "archive")
    if len(routes) != len(STEM_TO_SLUG) - 1:
        fail(f"expected {len(STEM_TO_SLUG) - 1} slug routes, found {len(routes)}")
    print(f"ok routes: / + {len(routes)} slugs")


def test_dom_matches_archive() -> None:
    """Generated DOM == the archive's DOM (the mirror is the oracle)."""
    for stem, slug in STEM_TO_SLUG.items():
        expected = skeleton(rewrite_page_html(archive_html(stem), stem, page_key(stem)))
        actual = skeleton(dist_page(slug).read_text(encoding="utf-8"))
        diff = first_difference(expected, actual)
        if diff:
            fail(f"{stem}: DOM differs from the archive: {diff}")
    print(f"ok dom: {len(STEM_TO_SLUG)} pages rebuild the archive's own markup")


def test_doctype() -> None:
    """The XHTML doctype is almost-standards mode; losing it shifts the layout."""
    for stem, slug in STEM_TO_SLUG.items():
        head = dist_page(slug).read_text(encoding="utf-8")[:400]
        if not head.startswith(XHTML_DOCTYPE):
            fail(f"{stem}: page does not start with the archive's XHTML doctype")
    print("ok doctype: XHTML 1.0 Transitional on every page")


def test_visible_text() -> None:
    for stem, slug in STEM_TO_SLUG.items():
        want = visible_text(archive_html(stem))
        got = visible_text(dist_page(slug).read_text(encoding="utf-8"))
        if want != got:
            i = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), 0)
            fail(
                f"{stem}: visible text differs at {i}: "
                f"archive={want[max(0, i - 40):i + 40]!r} dist={got[max(0, i - 40):i + 40]!r}"
            )
    print(f"ok text: {len(STEM_TO_SLUG)} pages show the archive's own words")


def test_header_blocks_present() -> None:
    """Regression: the iWeb text blocks that a clean re-theme dropped."""
    med = (DIST / "mediterranean-cruise" / "index.html").read_text(encoding="utf-8")
    if '<div class="text-content style_External_252_53"' not in med:
        fail("mediterranean-cruise lost the style_External_252_53 text block")
    if ">May 2008<" not in med:
        fail("mediterranean-cruise lost its 'May 2008' heading")
    for slug, heading in (
        ("peru", "Peru"),
        ("antarctica-2011", "Antarctica"),
        ("southern-africa", "Southern Africa"),
    ):
        page = (DIST / slug / "index.html").read_text(encoding="utf-8")
        if "text-content" not in page:
            fail(f"{slug} has no iWeb text-content block")
        if heading not in page:
            fail(f"{slug} lost its heading")
    home = (DIST / "index.html").read_text(encoding="utf-8")
    for needle in ("May 2009 — Southern Africa", "May 2008 — Mediterranean"):
        if needle not in home:
            fail(f"welcome page lost {needle!r}")
    print("ok header blocks: iWeb text content preserved")


def test_asset_prefix() -> None:
    """iWeb's toAbsoluteURL() prepends the page dir, so refs must be relative."""
    for stem, slug in STEM_TO_SLUG.items():
        html = dist_page(slug).read_text(encoding="utf-8")
        if re.search(r"[\"'(]/archive/", html):
            fail(f"{stem}: root-absolute /archive/ URL would 404 through iWeb's toAbsoluteURL()")
        if ASSET_PREFIX not in html:
            fail(f"{stem}: no {ASSET_PREFIX} references")
    print("ok asset prefix: all archive refs are relative")


def test_assets_exist() -> None:
    """Every referenced asset exists, and the missing ones are missing upstream."""
    missing_mirror: set[str] = set()
    missing_archive: set[str] = set()
    for stem, slug in STEM_TO_SLUG.items():
        for ref in archive_refs(archive_html(stem)):
            if not on_disk(ref):
                missing_archive.add(ref)
        for ref in mirror_refs(dist_page(slug).read_text(encoding="utf-8")):
            if not on_disk(ref):
                missing_mirror.add(ref)
    if not missing_mirror <= missing_archive:
        extra = sorted(missing_mirror - missing_archive)
        fail(f"the port references assets the archive does not have: {extra[:5]}")
    unexplained = [ref for ref in missing_archive if not any(k in ref for k in KNOWN_MISSING)]
    if unexplained:
        fail(f"archive refs missing on disk (not a known 404): {sorted(unexplained)[:5]}")
    print(f"ok assets: all refs resolve ({len(missing_archive)} known 404s, same as archive)")


def test_page_scripts_and_feeds() -> None:
    page_js = sorted((DIST / "page-js").glob("*.js"))
    feeds = sorted((DIST / "feeds").glob("*.xml"))
    if len(page_js) != len(STEM_TO_SLUG):
        fail(f"expected {len(STEM_TO_SLUG)} page scripts, found {len(page_js)}")
    for stem, slug in STEM_TO_SLUG.items():
        key = page_key(stem)
        js_src = TRAUT / f"{stem}_files" / f"{stem}.js"
        if not js_src.is_file():
            continue
        expected = rewrite_page_js(js_src.read_text(encoding="utf-8", errors="replace"), key)
        actual = (DIST / "page-js" / f"{key}.js").read_text(encoding="utf-8")
        if actual != expected:
            fail(f"{key}.js does not match the rewritten archive script")
        if "/archive/" in actual and ASSET_PREFIX not in actual:
            fail(f"{key}.js still uses root-absolute /archive/ paths")
        missing_mirror = {r[len(ASSET_PREFIX) :] for r in js_refs(actual) if not on_disk(r)}
        missing_archive = {
            r for r in js_refs(js_src.read_text(encoding="utf-8", errors="replace")) if not on_disk(r)
        }
        if not missing_mirror <= missing_archive:
            fail(
                f"{key}.js references assets the archive does not have: "
                f"{sorted(missing_mirror - missing_archive)[:5]}"
            )
        html = dist_page(slug).read_text(encoding="utf-8")
        if f"/page-js/{key}.js" not in html:
            fail(f"{stem} does not load /page-js/{key}.js")
    if len(feeds) != 27:
        fail(f"expected 27 page feeds, found {len(feeds)}")
    for feed in feeds:
        text = feed.read_text(encoding="utf-8")
        for ref in re.findall(r'url="([^"]+)"', text):
            if not on_disk(ref):
                fail(f"{feed.name}: enclosure {ref} missing")
        for ref in re.findall(r"<(?:iphoto:thumbnail|iweb:micro)>([^<]+)<", text):
            if not on_disk(ref):
                fail(f"{feed.name}: thumbnail {ref} missing")
        for link in re.findall(r"<link>([^<]+)</link>", text):
            path = link.split("#")[0]
            if path.endswith(".html"):
                fail(f"{feed.name}: feed still links to {link} instead of a clean route")
            if path not in ("", "/") and not path.startswith("/"):
                fail(f"{feed.name}: unexpected link {link}")
    print(f"ok scripts/feeds: {len(page_js)} page scripts, {len(feeds)} feeds")


def test_site_feed_and_navbar() -> None:
    feed = DIST / "feed.xml"
    if not feed.is_file():
        fail("dist/feed.xml missing (the iWeb navbar fetches it)")
    if feed.read_bytes() != (TRAUT / "feed.xml").read_bytes():
        fail("dist/feed.xml is not the archive's feed")
    for stem, slug in STEM_TO_SLUG.items():
        html = dist_page(slug).read_text(encoding="utf-8")
        if "new NavBar(" not in html:
            continue
        if re.search(r"new NavBar\(\s*'[^']*',\s*'[^']*',\s*'[^']*',\s*'\.'", html):
            fail(
                f"{stem}: NavBar sitePath '.' would fetch /{slug}/feed.xml; "
                "it must be '..' so the navbar feed resolves to /feed.xml"
            )
    print("ok navbar: sitePath '..' -> /feed.xml")


def test_welcome_alias() -> None:
    index = DIST / "index.html"
    alias = DIST / "Welcome.html"
    if not alias.is_file():
        fail("dist/Welcome.html alias missing")
    if alias.read_bytes() != index.read_bytes():
        fail("/Welcome.html is not byte-identical to /")
    print("ok welcome alias: /Welcome.html == /")


def test_redirect_stubs() -> None:
    expected = {f"{stem}.html": clean_route(stem) for stem in STEM_TO_SLUG}
    expected.pop("Welcome.html")
    expected.update({f"{name}.html": f"/{slug}" for name, slug in FILENAME_ALIASES.items()})
    for name, route in expected.items():
        stub = DIST / name
        if not stub.is_file():
            fail(f"missing redirect stub {name}")
        text = stub.read_text(encoding="utf-8")
        if f'url={route}"' not in text:
            fail(f"{name} does not redirect to {route}")
    stray = sorted(p.name for p in DIST.glob("*.html"))
    if len(stray) != len(expected) + 2:  # + index.html + Welcome.html
        fail(f"unexpected html at the site root: {stray}")
    print(f"ok redirect stubs: {len(expected)} old filenames still work")


def test_archive_untouched() -> None:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", "Traut.com"],
            cwd=ROOT.parent,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
        print(f"skip git check ({exc})")
        return
    if out:
        fail(f"Traut.com was modified:\n{out}")
    print("ok archive: Traut.com untouched")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print()
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
