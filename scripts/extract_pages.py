#!/usr/bin/env python3
"""Port Traut.com's iWeb pages into Astro data models.

Reads `Traut.com/<Stem>.html`, writes `src/data/pages/<key>.json` (one per page)
and `src/data/widgets.json` (the four iWeb widget chrome blocks, which are
identical on every page except their instance id and position).

Nothing is invented: every string in the model comes from the archive page, and
the extractor is strict -- an element it does not recognise aborts the build
instead of being silently dropped.

The URL rewriting is shared with `mirror_archive.py`, which also remains the
oracle used by `test_site.py` and the source of `/page-js` and `/feeds`.
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mirror_archive import (  # noqa: E402
    FEED_RE,
    NAVBAR_SITE_PATH_RE,
    STEM_TO_SLUG,
    TRAUT,
    clean_route,
    page_key,
    rewrite_js_paths,
    rewrite_url,
)

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "src" / "data" / "pages"
WIDGETS_JSON = ROOT / "src" / "data" / "widgets.json"

WIDGET_CLASSES = {
    "com-apple-iweb-widget-navbar": "navbar",
    "com-apple-iweb-widget-headercontrols": "headerControls",
    "com-apple-iweb-widget-detailview": "detailView",
    "com-apple-iweb-widget-footercontrols": "footerControls",
}

VOID = {"br", "img", "meta", "link", "input", "hr", "area", "base", "col", "param", "source"}
# Tags that may appear inside an iWeb rich-text block (p/div/a/span/br/img).
RICH_TAGS = {"p", "div", "a", "span", "br", "img", "em", "strong", "b", "i", "u"}


class Node:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag: str, attrs: dict[str, str] | None = None) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[Node] = []
        self.text = ""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.tag} {self.attrs} children={len(self.children)}>"


class TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return
        raise SystemExit(f"unbalanced </{tag}>")

    def handle_data(self, data):
        self.stack[-1].children.append(Node("#text"))
        self.stack[-1].children[-1].text = data

    def handle_comment(self, data):
        self.stack[-1].children.append(Node("#comment"))
        self.stack[-1].children[-1].text = data


def parse(html: str) -> Node:
    parser = TreeParser()
    parser.feed(html)
    return parser.root


def children(node: Node) -> list[Node]:
    return [c for c in node.children]


def element_children(node: Node) -> list[Node]:
    return [c for c in node.children if c.tag != "#text"]


def find(node: Node, tag: str, **attrs: str) -> Node | None:
    for child in element_children(node):
        if child.tag == tag and all(child.attrs.get(k) == v for k, v in attrs.items()):
            return child
        found = find(child, tag, **attrs)
        if found is not None:
            return found
    return None


def text_of(node: Node) -> str:
    if node.tag == "#text":
        return node.text
    return "".join(text_of(c) for c in node.children)


def norm_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# --------------------------------------------------------------------------- #
# rich text


def rich_node(node: Node) -> dict[str, Any]:
    """One node of a rich-text block -> JSON for <Node.astro>."""
    if node.tag == "#text":
        if not node.text:
            return {}
        return {"tag": "#text", "v": node.text}
    if node.tag not in RICH_TAGS:
        raise SystemExit(f"unsupported rich-text tag <{node.tag}> in {node.attrs}")
    attrs = dict(node.attrs)
    for key in ("href", "src"):
        if key in attrs:
            attrs[key] = rewrite_url(attrs[key])
    out: dict[str, Any] = {"tag": node.tag}
    if attrs:
        out["attrs"] = attrs
    kids = [rich_node(c) for c in node.children]
    kids = [k for k in kids if k]
    if kids:
        out["c"] = kids
    return out


# --------------------------------------------------------------------------- #
# head


def port_head(head: Node, stem: str, key: str) -> dict[str, Any]:
    """The head is an ordered list, comments included (IE conditional CSS)."""
    items: list[dict[str, Any]] = []
    title = ""
    for child in element_children(head):
        if child.tag == "#comment":
            # IE conditional stylesheets: rewrite the href inside the comment
            # too, exactly like mirror_archive's whole-document rewrite.
            items.append(
                {
                    "k": "comment",
                    "text": re.sub(
                        r"(href=['\"])([^'\"]+)(['\"])",
                        lambda m: m.group(1) + rewrite_url(m.group(2)) + m.group(3),
                        child.text,
                    ),
                }
            )
        elif child.tag == "meta":
            items.append({"k": "meta", "attrs": dict(child.attrs)})
        elif child.tag == "title":
            title = norm_ws(text_of(child))
            items.append({"k": "title", "text": title})
        elif child.tag == "link":
            attrs = dict(child.attrs)
            rel = attrs.get("rel", "")
            if rel == "stylesheet":
                attrs["href"] = rewrite_url(attrs.get("href", ""))
            elif rel == "alternate":
                attrs["href"] = f"/feeds/{key}.xml"
            else:
                raise SystemExit(f"{stem}: unsupported <link rel={rel!r}>")
            items.append({"k": "link", "attrs": attrs})
        elif child.tag == "style":
            text = text_of(child)
            text = re.sub(
                r"(@import\s+)([\"'])([^\"']+)\2",
                lambda m: f"{m.group(1)}{m.group(2)}{rewrite_url(m.group(3))}{m.group(2)}",
                text,
            )
            items.append({"k": "style", "attrs": dict(child.attrs), "text": text})
        elif child.tag == "script":
            src = child.attrs.get("src", "")
            if not src:
                raise SystemExit(f"{stem}: head <script> without src")
            # The page's own iWeb script sits next to the page CSS in
            # "<Stem>_files/<Stem>.js"; Utah's directory is percent-encoded, so
            # match the directory pattern instead of the stem.
            if re.search(r"[^/]+_files/[^/]+\.js$", src):
                src = f"/page-js/{key}.js"
            else:
                src = rewrite_url(src)
            items.append({"k": "script", "src": src})
        else:
            raise SystemExit(f"{stem}: unsupported head element <{child.tag}>")
    return {"title": title, "items": items}


# --------------------------------------------------------------------------- #
# body


def port_text_block(node: Node) -> dict[str, Any]:
    content = next(
        (c for c in element_children(node) if "text-content" in c.attrs.get("class", "")),
        None,
    )
    if content is None:
        raise SystemExit(f"text block without .text-content: {node.attrs}")
    return {
        "k": "text",
        "id": node.attrs.get("id") or None,
        "cls": node.attrs.get("class", ""),
        "style": node.attrs.get("style", ""),
        "contentCls": content.attrs.get("class", ""),
        "contentStyle": content.attrs.get("style", ""),
        "nodes": [n for n in (rich_node(c) for c in children(content)) if n],
    }


def port_widget(node: Node, init: str) -> dict[str, Any]:
    name = None
    for cls, widget in WIDGET_CLASSES.items():
        if cls in node.attrs.get("class", ""):
            name = widget
            break
    if name is None:
        raise SystemExit(f"unknown widget class: {node.attrs.get('class')}")
    scripts: list[str] = []
    inner = "".join(serialize(c, scripts) for c in children(node))
    segments = [
        {"t": "script", "v": scripts[int(m)]} if m.isdigit() else {"t": "html", "v": m}
        for m in re.split(r"\x00(\d+)\x00", inner)
        if m != ""
    ]
    return {
        "k": "widget",
        "name": name,
        "id": node.attrs["id"],
        "cls": node.attrs.get("class", ""),
        "style": node.attrs.get("style", ""),
        "init": init,
        "segments": segments,
    }


def serialize(node: Node, scripts: list[str] | None = None) -> str:
    """Raw HTML of a node (used for the widget chrome, which is pure boilerplate).

    Inline <script> children are replaced by NUL-delimited placeholders so the
    component can emit them as real script elements -- scripts injected through
    innerHTML never run, and these ones write the widget's localized labels.
    """
    if node.tag == "#comment":
        return f"<!--{node.text}-->"
    if node.tag == "script" and scripts is not None:
        scripts.append(text_of(node))
        return f"\x00{len(scripts) - 1}\x00"
    if node.tag == "#text":
        return (
            node.text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\xa0", "&nbsp;")
        )
    attrs = "".join(
        f' {k}="{v.replace("&", "&amp;").replace(chr(34), "&quot;")}"'
        for k, v in node.attrs.items()
    )
    if node.tag in VOID:
        return f"<{node.tag}{attrs} />"
    return f"<{node.tag}{attrs}>{''.join(serialize(c, scripts) for c in children(node))}</{node.tag}>"


def port_init_script(node: Node) -> str:
    text = text_of(node)
    text = rewrite_js_paths(text)
    text = FEED_RE.sub("@@FEED@@", text)
    text = NAVBAR_SITE_PATH_RE.sub(r"\1'..'", text)
    return text


def port_layer(node: Node, stem: str, feed_key: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    pending: Node | None = None
    for child in element_children(node):
        cls = child.attrs.get("class", "")
        if child.tag == "script":
            if pending is None:
                raise SystemExit(f"{stem}: <script> in layer without a widget")
            pending["init"] = port_init_script(child).replace("@@FEED@@", f"/feeds/{feed_key}.xml")
            pending = None
            continue
        if child.tag != "div":
            raise SystemExit(f"{stem}: unsupported <{child.tag}> in layer {node.attrs.get('id')}")
        if any(name in cls for name in ("bumper", "spacer", "tinyText")) or "shadow_" in cls:
            # Layout boxes. Usually a bare &nbsp;, but iWeb also parks image
            # blocks in .tinyText (the Welcome page's photo stack), so keep the
            # whole subtree.
            items.append(
                {
                    "k": "box",
                    "cls": cls,
                    "style": child.attrs.get("style", ""),
                    "nodes": [n for n in (rich_node(c) for c in children(child)) if n],
                }
            )
        elif "shape-with-text" in cls:
            items.append(port_text_block(child))
        elif "com-apple-iweb-widget-" in cls:
            widget = port_widget(child, "")
            items.append(widget)
            pending = widget
        elif child.attrs.get("id") and not cls:
            items.append({"k": "grid", "id": child.attrs["id"], "style": child.attrs.get("style", "")})
        else:
            raise SystemExit(f"{stem}: unsupported div in layer {node.attrs.get('id')}: {child.attrs}")
    if pending is not None:
        raise SystemExit(f"{stem}: widget {pending['id']} has no init script")
    return {"style": node.attrs.get("style", ""), "items": items}


def port_body(body: Node, stem: str, key: str) -> dict[str, Any]:
    centre = next((c for c in element_children(body) if c.tag == "div"), None)
    if centre is None:
        raise SystemExit(f"{stem}: no body wrapper")
    content = next(
        (c for c in element_children(centre) if c.attrs.get("id") == "body_content"), None
    )
    if content is None:
        raise SystemExit(f"{stem}: no #body_content")
    layers: dict[str, Any] = {}
    for child in element_children(content):
        layer_id = child.attrs.get("id", "")
        name = {
            "nav_layer": "nav",
            "header_layer": "header",
            "body_layer": "body",
            "footer_layer": "footer",
        }.get(layer_id)
        if name is None:
            raise SystemExit(f"{stem}: unsupported child of #body_content: {child.attrs}")
        layers[name] = port_layer(child, stem, key)
    for required in ("nav", "header", "body", "footer"):
        if required not in layers:
            raise SystemExit(f"{stem}: missing {required}_layer")
    return {
        "attrs": dict(body.attrs),
        "wrapperStyle": centre.attrs.get("style", ""),
        "contentStyle": content.attrs.get("style", ""),
        **layers,
    }


# --------------------------------------------------------------------------- #


def port_page(stem: str) -> tuple[str, dict[str, Any], dict[str, str]]:
    key = page_key(stem)
    src = TRAUT / f"{stem}.html"
    root = parse(src.read_text(encoding="utf-8", errors="replace"))
    html = next(c for c in element_children(root) if c.tag == "html")
    head = next(c for c in element_children(html) if c.tag == "head")
    body = next(c for c in element_children(html) if c.tag == "body")

    model: dict[str, Any] = {
        "key": key,
        "stem": stem,
        "slug": clean_route(stem),
        "htmlAttrs": dict(html.attrs),
        "head": port_head(head, stem, key),
        "body": port_body(body, stem, key),
    }
    widgets: dict[str, list[dict[str, str]]] = {}
    for layer in ("nav", "header", "body", "footer"):
        for item in model["body"][layer]["items"]:
            if item["k"] == "widget":
                segments = [
                    {"t": seg["t"], "v": seg["v"].replace(item["id"], "@@ID@@")}
                    for seg in item["segments"]
                ]
                prev = widgets.get(item["name"])
                if prev is not None and prev != segments:
                    raise SystemExit(
                        f"{stem}: widget {item['name']} markup differs from the other pages"
                    )
                widgets[item["name"]] = segments
                item.pop("segments")
    return key, model, widgets


def main() -> int:
    if not TRAUT.is_dir():
        print("missing Traut.com archive", file=sys.stderr)
        return 1
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    for old in PAGES_DIR.glob("*.json"):
        old.unlink()
    all_widgets: dict[str, str] = {}
    for stem in STEM_TO_SLUG:
        key, model, widgets = port_page(stem)
        (PAGES_DIR / f"{key}.json").write_text(
            json.dumps(model, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        all_widgets.update(widgets)
    WIDGETS_JSON.write_text(
        json.dumps(all_widgets, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        f"extract_pages: {len(STEM_TO_SLUG)} page models, "
        f"{len(all_widgets)} widget chrome blocks -> {PAGES_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
