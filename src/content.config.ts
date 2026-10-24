// The `pages` content collection: one entry per archived iWeb page, generated
// by scripts/extract_pages.py from Traut.com/<Stem>.html.
//
// The schema is the contract between that extractor and the components in
// src/components/. `test_site.py` proves the rendered DOM still matches the
// archive; this proves the *model* is what the templates think it is, with a
// readable error instead of `undefined is not a function` at render time.
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const attrs = z.record(z.string(), z.string());

/** Rich text: text, <br>, <a>, <span>, <img>, … (recursive). */
const richNode: z.ZodType<unknown> = z.lazy(() =>
  z.union([
    z.object({ tag: z.literal('#text'), v: z.string() }),
    z.object({
      tag: z.string(),
      attrs: attrs.optional(),
      c: z.array(richNode).optional(),
    }),
  ]),
);

/**
 * Inline geometry, as an ordered map of CSS declarations. iWeb's own runtime
 * reads it back off the DOM (`spacer.style.height`, `photogrid.style.top`), so
 * it is rendered as a style attribute; see src/engine/geometry.ts.
 */
const box = z.partialRecord(
  z.enum([
    'position',
    'left',
    'top',
    'width',
    'height',
    'z-index',
    'margin-left',
    'margin-top',
    'opacity',
    'line-height',
    'float',
    'clear',
  ]),
  z.string(),
);

const widgetName = z.enum(['navbar', 'headerControls', 'detailView', 'footerControls']);

const textItem = z.object({
  k: z.literal('text'),
  id: z.string().nullable(),
  cls: z.string(),
  box,
  contentCls: z.string(),
  contentStyle: z.string(),
  nodes: z.array(richNode),
});

const boxItem = z.object({
  k: z.literal('box'),
  cls: z.string(),
  box,
  nodes: z.array(richNode),
});

const widgetItem = z.object({
  k: z.literal('widget'),
  name: widgetName,
  id: z.string(),
  cls: z.string(),
  box,
  /** The page's own `new Widget(...)` call, verbatim. */
  init: z.string(),
});

const gridItem = z.object({
  k: z.literal('grid'),
  id: z.string(),
  box,
});

const layer = z.object({
  box,
  items: z.array(z.discriminatedUnion('k', [textItem, boxItem, widgetItem, gridItem])),
});

const headItem = z.discriminatedUnion('k', [
  z.object({ k: z.literal('meta'), attrs }),
  z.object({ k: z.literal('title'), text: z.string() }),
  z.object({ k: z.literal('pageCss'), attrs }),
  z.object({ k: z.literal('widgetCss'), name: widgetName, attrs }),
  z.object({ k: z.literal('link'), attrs }),
  z.object({ k: z.literal('comment'), text: z.string() }),
  z.object({ k: z.literal('style'), attrs, text: z.string() }),
  z.object({ k: z.literal('script'), src: z.string() }),
]);

const pages = defineCollection({
  // Entry id = the archive page key (`peru`, `index`, …), not a slugified path.
  loader: glob({
    pattern: '*.json',
    base: './src/content/pages',
    generateId: ({ entry }) => entry.replace(/\.json$/, ''),
  }),
  schema: z.object({
    key: z.string(),
    stem: z.string(),
    slug: z.string(),
    htmlAttrs: attrs,
    head: z.object({ title: z.string(), items: z.array(headItem) }),
    body: z.object({
      attrs,
      wrapperStyle: z.string(),
      contentStyle: z.string(),
      nav: layer,
      header: layer,
      body: layer,
      footer: layer,
    }),
  }),
});

export const collections = { pages };
