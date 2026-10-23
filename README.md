# traut.com — an Astro port of an archived iWeb site

Eric Traut's old iWeb travel site (`traut.com`) rebuilt as a static Astro site:
31 routes, real `.astro` layouts and components, one data model per archive
page, and every page still renders **pixel-identically** to the archived
original — including its photo grids, slideshows and widget chrome, which keep
running on the archive's own iWeb JavaScript.

```bash
npm install
npm run build      # extract models -> mirror assets -> astro build
npm test           # 14 structural checks (markup, URLs, assets, feeds)
npm run pixels     # 31/31 pages, full-page, zero differing pixels
npm run audit      # 31/31 pages, identical DOM *after* iWeb's JS has run
npm run dev        # predev generates public/ first, so the grids work
```

The archive itself (`Traut.com/`, 285 MB of iWeb HTML, CSS, JS and photos) is
**not** part of this repository. It is expected next to it:

```
etraut/
├── Traut.com/      # the untouched archive (read-only input)
└── astro_traut2/   # this project
```

Nothing here ever writes to `Traut.com/`.

## Architecture

A page is built in three steps, none of which hand-writes archive content:

```
Traut.com/Peru.html ──scripts/extract_pages.py──▶ src/data/pages/peru.json
                                                  src/data/widgets.json
src/pages/[slug].astro ──layouts/Page.astro──▶ dist/peru/index.html
```

**1. `scripts/extract_pages.py` — archive → data model.** A strict, comment-aware
HTML parser walks each archive page and writes a JSON model: the `<head>` as an
ordered list of items (metas, title, stylesheet links, IE conditional comments,
`@import` blocks, RSS link, scripts), the `<body>` attributes, the four iWeb
layers (`nav`, `header`, `body`, `footer`) and, inside them, every item:

| Model | From the archive | Rendered by |
| --- | --- | --- |
| `text` | `div.shape-with-text` → `.text-content` → rich text (`p`, `div`, `a`, `span`, `br`, `img`) | `TextBlock.astro` + `Node.astro` (recursive) |
| `box` | `bumper` / `spacer` / `tinyText` layout boxes (a `&nbsp;`, an image block, a shadow) | `Layer.astro` |
| `widget` | the four iWeb widgets (`NavBar`, `HeaderControls`, `DetailView`, `FooterControls`) | `Widget.astro` |
| `grid` | the empty positioned div that the page's own script fills with photos | `PhotoGrid.astro` |

The parser is strict: an element it does not recognise aborts the build instead
of being silently dropped. That is deliberate — the whole point of this port is
that nothing gets lost on the way.

**2. `src/data/widgets.json` — the shared widget chrome.** The four widget
markups are byte-identical on all 31 pages except for their instance id and
position, so they are stored once, with `@@ID@@` placeholders, and split at
their inline `<script>` nodes. The split matters: scripts injected through
`innerHTML` never execute, and those scripts are what write the widget's
localized labels ("Subscribe", "Play Slideshow", "n of m"). `Widget.astro` emits
them as real `<script>` elements, in place, in order.

**3. Astro renders it.** `src/pages/[slug].astro` builds one route per model with
`getStaticPaths()` over `import.meta.glob('../data/pages/*.json')`; `/` is the
Welcome page. Both hand the model to `layouts/Page.astro`, which renders the
`<html>` shell, `Head.astro`, and the four layers through `Layer.astro` →
`TextBlock` / `Widget` / `PhotoGrid` / boxes.

**4. The CSS is the archive's, imported through Astro.** iWeb generated one
stylesheet per page (`Peru_files/Peru.css`) plus three widget stylesheets; those
files *are* the site's typography and layout, so `scripts/sync_styles.py` copies
them into `src/styles/pages/*.css` and `src/styles/widgets/*.css` (byte-for-byte,
with a one-line provenance header) and the build imports them the Astro way:

* `src/engine/styles.ts` maps each stylesheet through
  `import.meta.glob('…/*.css', { query: '?url' })`, so Vite emits it as a
  content-hashed asset and `Head.astro` links exactly one per route
  (`/_astro/peru.<hash>.css`);
* the three widget stylesheets stay the archive's own
  `<style><!-- @import "…"; --></style>` blocks, in the archive's order, so the
  cascade order (page sheet first, then HeaderControls, DetailView,
  FooterControls) is unchanged;
* `scripts/sync_styles.py --check` runs in `prebuild` and `npm test`, so a copy
  can never silently drift from the archive.

Everything else — the photo grid layout, captions, slideshow, detail view,
navbar, pagination, text auto-fit — is the archive's own `Scripts/*.js` and each
page's own script, loaded from `/page-js/<key>.js`. This is a port of the
markup, not a re-implementation of iWeb.

### Why the geometry stays an inline `style`

Every layer, text block, spacer and photo grid carries the archive's original
inline `style` attribute verbatim, and the components render it as-is. That is
not laziness: iWeb's runtime *reads it back off the DOM*.

```js
// Scripts/iWebMediaGrid.js -- grow the layer's last spacer to fit the grid
initialSpacerHeight = parseInt(spacer.style.height);
spacerHeight = Math.max(parseInt(photogrid.style.top) + height - spacer.offsetTop,
                        initialSpacerHeight);

// Scripts/iWebSite.js -- the height the text has to fit in
if (oTextBoxOuterDiv.style.height !== "")
  specifiedHeight = parseFloat(oTextBoxOuterDiv.style.height);
```

An earlier revision of this port moved the geometry into CSS custom properties
(`--iw-height: 40px`) with the rules in component `<style>` blocks. It looked
tidier, and every album page collapsed: `style.height` read back as `""`,
`parseInt("")` is `NaN`, and the spacer that should have grown to 2035 px stayed
at its initial 382 px. The same applies to text auto-fit, which then never
shrinks anything.

So the split is: **geometry stays inline** (it is data, and the runtime's input);
**everything that is CSS stays CSS** (the archive's stylesheets, imported and
bundled through Astro). Components still own the structure — they decide what a
layer, text block, widget or grid *is* — but they do not re-declare the numbers
the original scripts depend on.

### URL plumbing

The only changes made to the original markup:

| Change | Why |
| --- | --- |
| `Peru_files/…`, `Media/…`, `Scripts/…` → `../archive/…` | Assets stay in `Traut.com/`, served through the `public/archive` symlink. The prefix **must be relative**: iWeb's `String#toAbsoluteURL()` prepends the document directory to any URL without `:/`, so `/archive/…` would be fetched as `/peru//archive/…` and every photo grid would come up empty. |
| `Peru.html` → `/peru` | Clean routes. |
| `<page>_files/<page>.js` → `/page-js/<key>.js` | A rewritten copy of the page's own script, so its relative asset paths resolve. |
| `<page>_files/rss.xml` → `/feeds/<key>.xml` | A rewritten copy of the page's photo feed (enclosures, thumbnails, `<link>`s). |
| `new NavBar(…, '.', …)` → `new NavBar(…, '..', …)` | The navbar fetches `<sitePath>/feed.xml`. The archive sat at the site root; these routes are one level down. |
| `<!DOCTYPE html>` → the XHTML 1.0 Transitional doctype | See below. |

### The doctype is load-bearing

Astro always writes `<!DOCTYPE html>`, whatever the template declares. That
silently changes the rendering mode: iWeb's XHTML 1.0 Transitional doctype puts
Chromium in **almost standards mode**, where a line box holding an inline-block
image does not get the strut descender. Under `<!DOCTYPE html>` every photo
block grows ~3 px, iWeb's own `adjustLineHeightIfTooBig()` then shrinks the
line-height (14 px → 13.3 px), and the page drifts from the archive.

`integrations/iweb-doctype.mjs` restores the archive's doctype on every built
page in `astro:build:done`. It is the one piece of the original markup Astro
will not let a template control.

### Build steps

| Step | Command | What it does |
| --- | --- | --- |
| `predev` / `prebuild` | `scripts/extract_pages.py` | archive → `src/data/pages/*.json`, `src/data/widgets.json` |
| `predev` / `prebuild` | `scripts/mirror_archive.py` | writes `public/page-js/*.js`, `public/feeds/*.xml`, `public/feed.xml`, `public/archive` symlink and the 31 redirect stubs |
| `predev` / `prebuild` | `scripts/sync_styles.py --check` | fails the build if `src/styles/**` drifted from the archive's CSS |
| `build` | `astro build` | renders the 31 routes and bundles the stylesheets; `integrations/iweb-doctype.mjs` restores the doctype |
| `postbuild` | `mirror_archive.relink_dist_archive()` | turns `dist/archive` back into a symlink (Astro would copy 285 MB by value) |
| `postbuild` | `mirror_archive.publish_welcome_alias()` | `dist/Welcome.html` as a copy of `dist/index.html` |

## Routes

All 31 archive pages have a route; `/` is `Welcome.html`.

| Route | Archive file |
| --- | --- |
| `/` | `Welcome.html` |
| `/antarctic-peninsula` | `Antarctic_Peninsula.html` |
| `/antarctica-2011` | `Antarctica_2011.html` |
| `/around-the-world` | `Around_The_World.html` |
| `/australia` | `Australia.html` |
| `/cambodia` | `Cambodia.html` |
| `/china` | `China.html` |
| `/easter-island` | `Easter_Island.html` |
| `/egypt` | `Egypt.html` |
| `/falkland-islands` | `Falkland_Islands.html` |
| `/glacier-2010` | `Glacier_2010.html` |
| `/iceland-2011` | `Iceland_2011.html` |
| `/india` | `India.html` |
| `/mediterranean-cruise` | `Mediterranean_Cruise.html` |
| `/morocco` | `Morocco.html` |
| `/northern-namibia` | `Northern_Namibia.html` |
| `/okavango-delta` | `Okavango_Delta.html` |
| `/patagonia` | `Patagonia.html` |
| `/peru` | `Peru.html` |
| `/south-georgia` | `South_Georgia.html` |
| `/southern-africa` | `Southern_Africa.html` |
| `/tanzania` | `Tanzania.html` |
| `/tetons-2011` | `Tetons_2011.html` |
| `/tibet` | `Tibet.html` |
| `/utah-arizona` | `Utah_&_Arizona.html` |
| `/washington-dc` | `Washington_DC.html` |
| `/windhoek-and-sossusvlei` | `Windhoek_and_Sossusvlei.html` |
| `/wrangell-island-2013` | `Wrangell_Island_2013.html` |
| `/yellowstone-2013` | `Yellowstone_2013.html` |
| `/yosemite-2010` | `Yosemite_2010.html` |
| `/zambia-and-chobe` | `Zambia_and_Chobe.html` |

Four of them (`Welcome`, `Antarctica_2011`, `Around_The_World`,
`Southern_Africa`) are iWeb *collection* pages: a title, prose and a stack of
child-album thumbnails rather than a photo grid. The other 27 are albums with a
photo grid and an RSS photo feed.

## What was missing before

An earlier version of this folder was a *re-implementation*: it extracted the
titles, prose and photo lists out of the archive and rebuilt them with an Astro
layout and one hand-written stylesheet. It looked plausible, but it was not the
original page, and this is the complete list of what that approach lost.

### 1. iWeb text blocks, including the date headings

Every page has a `header_layer` with `shape-with-text` divs. The album date
heading is one of them — for example, on `/mediterranean-cruise`:

```html
<div id="id2" style="height: 53px; left: 428px; position: absolute; top: 7px; width: 252px; z-index: 1;" class="style_SkipStroke_1 shape-with-text">
  <div class="text-content style_External_252_53" style="padding: 0px; ">
    <div class="style_1">
      <p style="padding-bottom: 0pt; padding-top: 0pt; " class="Heading_1">May 2008</p>
    </div>
  </div>
</div>
```

The re-implementation dropped that whole block: the page title survived, the
date did not. The same applied to:

* the `body_layer` intro/aside prose (`text-content style_External_*` with
  `Body`, `Heading_1`, `paragraph_style` and `style_1…style_4` runs, nested
  `<span>`s, `<br />`s and line-height overrides) — the re-theme re-typed the
  words into its own markup, so paragraph breaks, italics and spacing drifted;
* the per-page `shape-with-text` geometry (absolute `left`/`top`/`width`/
  `height` per block) and the `style_SkipStroke` classes;
* iWeb's text auto-fit (`adjustLineHeightIfTooBig` / `adjustFontSizeIfTooBig`,
  called from each page's own script) which shrinks line-height and font size
  when a block overflows — the re-theme had no such thing.

### 2. The per-album iWeb stylesheets

`Peru_files/Peru.css`, `…IE.css` and `…Moz.css` are generated per page and carry
the real typography (`.Header`, `.Heading_1`, `.Body`, `.Caption`, `.paragraph_style`,
text shadows, the 700 px canvas, the `rgb(101, 101, 101)` page field, the white
content box). The re-implementation replaced them with a single generic
`traut.css`, so every album was re-styled rather than reproduced.

### 3. iWeb widget chrome

Four widgets are instantiated in each page's inline script and each one was
missing entirely:

| Widget | What it is |
| --- | --- |
| `NavBar` | the top site link, generated at runtime from `/feed.xml` |
| `HeaderControls` | "back to index", the RSS **subscribe** button, "play slideshow" |
| `FooterControls` | pagination (previous / next page of a large album) |
| `DetailView` | the large-photo view: caption, "n of m", arrow transport, close |

The `DetailView` is what you get when you open `#0` (or click a thumbnail); it
was simply absent before, as were the subscribe link, the slideshow button and
the pagination arrows.

### 4. The photo grid geometry and its frames/shadows

The grid is not "a CSS grid of thumbnails". Each album's script calls

```js
IWLayoutPhotoGrid('id2', new IWPhotoGridLayout(4, new IWSize(149,149),
  new IWSize(149,28), new IWSize(162,192), 27, 27, 0, new IWSize(19,19)),
  new IWPhotoFrame([…Watercolor_iweb_*.png…], …), …)
```

i.e. column count, thumbnail size, caption band height, cell size, horizontal
and vertical gaps, frame borders, and the `IWShadow` drop shadow (blur 10,
offset 4.2426, `rgba(0,0,0,0.75)`) — all computed at runtime. Captions come from
the `<iweb:richTitle>` HTML inside each page's `rss.xml`, not from a text field
in a database. A re-implementation approximates this; it cannot match it.

### 5. Canvas, layers and control art

`body { background: rgb(101,101,101) }`, the 700 px white content column,
`#header_layer` / `#body_layer` / `#footer_layer` stacking, and the
`Media/canvas_*` control images (transport arrows, play, thumbs, subscribe,
download) with their N/D/S variants. The re-theme had a flat white page.

### 6. Feeds, slideshow popup and deep links

* the per-page RSS photo feed (`Peru_files/rss.xml`) and the subscribe button
  that opens it;
* the slideshow popup (`Media/slideshow.html` + `Scripts/iWPopUpSlideshow.js`,
  `Media/iWPopUpSlideshow.css`) with its own full-screen chrome;
* `#N` fragment deep links into the detail view;
* the site navbar feed `feed.xml` — without it the navbar renders no link at
  all (that was the last 58 × 9 px of difference at the top right of every
  album page).

### 7. Collection pages

`/antarctica-2011`, `/around-the-world` and `/southern-africa` are iWeb
collection pages: they lay out child-album thumbnails with their own grid
layout, dates and prose. The re-implementation flattened them into link lists.

## What the port guarantees

Because every route is rendered from the archive's own structure, all of the
above is present by construction. `npm test` pins it down:

```
ok archive: Traut.com untouched
ok asset prefix: all archive refs are relative
ok assets: all refs resolve (0 known 404s, same as archive)
ok routes: / + 30 slugs
ok doctype: XHTML 1.0 Transitional on every page
ok dom: 31 pages rebuild the archive's own markup
ok header blocks: iWeb text content preserved
ok models: 31 page models
ok scripts/feeds: 31 page scripts, 27 feeds
ok redirect stubs: 31 old filenames still work
ok navbar: sitePath '..' -> /feed.xml
ok stylesheets: 31 page sheets + widget sheets, bundled
ok text: 31 pages show the archive's own words
ok welcome alias: /Welcome.html == /
```

`test_site.py` compares each built page's DOM against
`mirror_archive.rewrite_page_html()` — the archive HTML with only the URL
plumbing applied — so a dropped block, changed class, lost caption or mangled
script fails the build. The only attributes it normalises are the stylesheet
URLs Astro content-hashes (`/_astro/peru.<hash>.css`); `test_stylesheets` checks
those links and imports separately, plus that `src/styles/**` still matches the
archive byte for byte. Byte equality is not the bar: Astro rewrites the
doctype, self-closing tags and inter-element whitespace by design. The bar is
the DOM plus the pixels.

Pixel verification (headless Chromium, 800 px wide, **full page**) against
`Traut.com/*.html` served from a local static server: all 31 pages are
pixel-identical (zero differing pixels). Reproduce it with:

```bash
npm run build
python3 scripts/verify_pixels.py          # all 31 routes
python3 scripts/verify_pixels.py peru     # or a subset
```

The screenshots used to be viewport-sized (`--screenshot` with an 800 × 1400
window), which silently compared only the top 1400 px of pages up to 2905 px
tall. `scripts/shot.mjs` now drives the DevTools protocol and clips to the
document's real content size, so the whole photo grid is compared.

`npm run audit` (`scripts/audit_runtime.mjs`) closes the other half of the gap:
`test_site.py` compares the markup Astro emits, but the photo grid, the
`.framedImage` wrappers and their shadows, the captions and the widget labels
only exist *after* iWeb's JavaScript runs. The audit loads both versions in
Chromium, waits for the scripts, and compares the resulting DOM — every element,
class, id, inline `style` and text node — plus the document height and the
`.framedImage`/`img` counts:

```
peru                     ok    framedImage 38/38  img 1926/1926  height 2336/2336
```

`scripts/probe_layout.mjs` is the debugging companion used when a page differed:
it evaluates a JS expression (element geometry, computed styles, console errors)
in headless Chromium via the DevTools protocol.

## Known archive quirks, kept as-is

* `Peru_files/Watercolor_iweb_01.png` and friends are referenced by the grid
  frames but do not exist in the archive; they 404 on traut.com too. The grid
  still lays out identically, so they stay broken here as well — inventing them
  would be a change to the original design.
* `Utah_&_Arizona.html` is the real file; `Utah_%26_Arizona.html` and
  `Utah_%26_Arizona_files` are symlinks in the archive. Both stems map to
  `/utah-arizona`, and its page script is matched by directory pattern rather
  than by stem.
* The archive's `index.html` is a meta-refresh to `Welcome.html`; here `/` *is*
  the Welcome page, and `/Welcome.html` is an alias for it.
* URLs have no trailing slash (`/peru`); the build emits `peru/index.html`, so
  a static host should serve `peru/index.html` for `/peru`. Relative asset
  paths (`../archive/…`) resolve the same with or without the trailing slash.

## Layout

```
astro.config.mjs          Astro config (static, directory format, iWeb doctype)
integrations/             iweb-doctype.mjs — restore the XHTML doctype
src/pages/                index.astro (Welcome), [slug].astro (one per model)
src/layouts/Page.astro    html/head/body shell, four layers
src/components/           Head, Layer, TextBlock, Node, Widget, PhotoGrid
src/styles/pages/*.css    the archive's per-page stylesheets (generated copies)
src/styles/widgets/*.css  the three archive widget stylesheets (generated copies)
src/engine/styles.ts      ?url globs: page/widget stylesheet -> bundled asset URL
src/data/pages/*.json     one model per archive page (generated)
src/data/widgets.json     the four widget chrome blocks (generated)
src/engine/types.ts       the model types the components consume
scripts/extract_pages.py  archive -> models (strict)
scripts/sync_styles.py    archive CSS -> src/styles (byte-equal, --check)
scripts/mirror_archive.py URL plumbing, page scripts, feeds, stubs, oracle
scripts/verify_pixels.py  full-page screenshot diff against the archive
scripts/shot.mjs          full-page screenshot via the DevTools protocol
scripts/audit_runtime.mjs post-JS DOM diff against the archive (npm run audit)
scripts/test_site.py      structural tests (npm test)
scripts/probe_layout.mjs  headless-Chromium expression probe
```
