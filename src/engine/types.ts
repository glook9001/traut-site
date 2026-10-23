// Types for the ported iWeb page model (see scripts/extract_pages.py).

export type Attrs = Record<string, string>;

/** One node of an iWeb rich-text block: text, <br>, <a>, <span>, <img>, … */
export type RichNode =
  | { tag: '#text'; v: string }
  | { tag: string; attrs?: Attrs; c?: RichNode[] };

/** A `shape-with-text` block: the header title, the album date, prose, a footer note. */
export interface TextItem {
  k: 'text';
  id: string | null;
  cls: string;
  /** The archive's inline style, verbatim: iWeb's runtime reads it back. */
  style: string;
  contentCls: string;
  contentStyle: string;
  nodes: RichNode[];
}

/** bumper / tinyText / spacer: iWeb layout boxes (usually one &nbsp;, sometimes an image block). */
export interface BoxItem {
  k: 'box';
  cls: string;
  style: string;
  nodes: RichNode[];
}

export type WidgetName = 'navbar' | 'headerControls' | 'detailView' | 'footerControls';

/** An iWeb widget instance: fixed chrome from src/data/widgets.json + this page's id/position/init. */
export interface WidgetItem {
  k: 'widget';
  name: WidgetName;
  id: string;
  cls: string;
  style: string;
  /** The page's own `new Widget(...)` call, verbatim. */
  init: string;
}

/** Widget chrome split at its inline <script> nodes, which must stay real elements. */
export interface WidgetSegment {
  t: 'html' | 'script';
  v: string;
}

/** The empty div the page's own script fills with the photo grid. */
export interface GridItem {
  k: 'grid';
  id: string;
  style: string;
}

export type LayerItem = TextItem | BoxItem | WidgetItem | GridItem;

export interface Layer {
  style: string;
  items: LayerItem[];
}

export type HeadItem =
  | { k: 'meta'; attrs: Attrs }
  | { k: 'title'; text: string }
  /** The page's own iWeb stylesheet (src/styles/pages/<key>.css). */
  | { k: 'pageCss'; attrs: Attrs }
  /** One of the shared widget stylesheets, kept as its own @import block. */
  | { k: 'widgetCss'; name: WidgetName; attrs: Attrs }
  | { k: 'link'; attrs: Attrs }
  | { k: 'comment'; text: string }
  | { k: 'style'; attrs: Attrs; text: string }
  | { k: 'script'; src: string };

export interface Page {
  key: string;
  stem: string;
  slug: string;
  htmlAttrs: Attrs;
  head: { title: string; items: HeadItem[] };
  body: {
    attrs: Attrs;
    wrapperStyle: string;
    contentStyle: string;
    nav: Layer;
    header: Layer;
    body: Layer;
    footer: Layer;
  };
}

export type WidgetChrome = Record<WidgetName, WidgetSegment[]>;
