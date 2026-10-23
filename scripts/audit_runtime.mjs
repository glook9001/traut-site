#!/usr/bin/env node
/**
 * Compare the archive and the port *after* iWeb's JavaScript has run.
 *
 * `test_site.py` compares the markup Astro emits, which is the archive's markup
 * before iWeb's scripts touch it. A lot of the page only exists afterwards: the
 * photo grid (`IWLayoutPhotoGrid`), the `.framedImage` wrappers and their
 * shadows, the widget labels, the detail view. This script loads both versions
 * in headless Chromium, waits for the scripts, and compares the resulting DOM.
 *
 *   node scripts/audit_runtime.mjs                 # all routes
 *   node scripts/audit_runtime.mjs peru index      # a subset
 *
 * Needs the build (`npm run build`) and Pillow-free; only Chromium is required.
 */
import { execSync, spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const TRAUT = join(ROOT, '..', 'Traut.com');
const DIST = join(ROOT, 'dist');

// Archive stem -> route slug (kept in step with scripts/mirror_archive.py).
const ROUTES = JSON.parse(
  execSync('python3 -c "import sys,json;sys.path.insert(0,\'scripts\');from mirror_archive import STEM_TO_SLUG;print(json.dumps(STEM_TO_SLUG))"', {
    cwd: ROOT,
  }).toString(),
);

const only = process.argv.slice(2);
const routes = Object.entries(ROUTES).filter(
  ([stem, slug]) => only.length === 0 || only.includes(slug || 'index') || only.includes(stem),
);

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
};

function serve(root, port) {
  const server = createServer(async (req, res) => {
    try {
      const url = decodeURIComponent((req.url || '/').split('?')[0].split('#')[0]);
      let file = normalize(join(root, url));
      if (!file.startsWith(root)) throw new Error('outside root');
      if ((await stat(file)).isDirectory()) file = join(file, 'index.html');
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': TYPES[extname(file)] ?? 'application/octet-stream' });
      res.end(body);
    } catch {
      res.writeHead(404, { 'content-type': 'text/plain' });
      res.end('not found');
    }
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve(server)));
}

const chrome =
  process.env.CHROME ??
  execSync('ls -d ~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell 2>/dev/null | tail -1', {
    shell: '/bin/sh',
  })
    .toString()
    .trim();
if (!chrome) throw new Error('no Chromium found; set $CHROME');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const debugPort = 9800 + Math.floor(Math.random() * 150);
const proc = spawn(chrome, [
  '--headless',
  '--disable-gpu',
  '--hide-scrollbars',
  `--remote-debugging-port=${debugPort}`,
  '--window-size=800,1400',
  'about:blank',
]);

async function endpoint() {
  for (let i = 0; i < 100; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
      return (await res.json()).webSocketDebuggerUrl;
    } catch {
      await sleep(100);
    }
  }
  throw new Error('chrome did not start');
}

const ws = new WebSocket(await endpoint());
await new Promise((r) => ws.addEventListener('open', r, { once: true }));

let id = 0;
const pending = new Map();
const events = [];
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  } else if (msg.method) {
    events.push(msg);
  }
});

function send(method, params = {}, sessionId) {
  const msgId = ++id;
  ws.send(JSON.stringify({ id: msgId, method, params, sessionId }));
  return new Promise((r) => pending.set(msgId, r));
}

const { result: target } = await send('Target.createTarget', { url: 'about:blank' });
const { result: attached } = await send('Target.attachToTarget', { targetId: target.targetId, flatten: true });
const { sessionId } = attached;
await send('Runtime.enable', {}, sessionId);
await send('Page.enable', {}, sessionId);

/**
 * The page as the browser ends up with it: every element's tag, attributes
 * (inline `style` included -- that is what iWeb's layout writes) and text.
 *
 * URL-valued attributes and <script>/<style> bodies are left out: those are the
 * URL plumbing, and `test_site.py` already compares them against the oracle.
 * What is left is the part only the runtime can produce -- the photo grid, the
 * `.framedImage` wrappers, the shadows, the captions, the widget labels.
 */
const SNAPSHOT = `(() => {
  const walk = (el) => {
    if (el.nodeType === 3) {
      const text = el.nodeValue.replace(/\\s+/g, ' ');
      return text.trim() ? ['#text', text] : null;
    }
    if (el.nodeType !== 1) return null;
    const tag = el.tagName.toLowerCase();
    const attrs = {};
    for (const a of el.attributes) {
      if (a.name.startsWith('data-astro-')) continue;
      if (a.name === 'href' || a.name === 'src') continue;
      attrs[a.name] = a.value;
    }
    const kids = [];
    if (tag !== 'script' && tag !== 'style') {
      for (const child of el.childNodes) {
        const node = walk(child);
        if (node) kids.push(node);
      }
    }
    return [tag, attrs, kids];
  };
  const counts = {};
  for (const sel of ['.framedImage', 'img', '#body_layer .spacer']) {
    counts[sel] = document.querySelectorAll(sel).length;
  }
  return { tree: walk(document.documentElement), counts, height: document.documentElement.scrollHeight };
})()`;

const errors = [];
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.method === 'Runtime.exceptionThrown' && msg.sessionId === sessionId) {
    errors.push(msg.params.exceptionDetails.exception?.description ?? msg.params.exceptionDetails.text);
  }
});

async function snapshot(url) {
  errors.length = 0;
  await send('Page.navigate', { url }, sessionId);
  await sleep(2600);
  const { result } = await send(
    'Runtime.evaluate',
    { expression: SNAPSHOT, returnByValue: true, awaitPromise: true },
    sessionId,
  );
  return { ...result.result.value, errors: [...errors] };
}

function firstDiff(a, b, path = '') {
  if (typeof a !== typeof b) return `${path}: ${typeof a} != ${typeof b}`;
  if (Array.isArray(a)) {
    if (a.length !== b.length) {
      return `${path}: ${a.length} nodes != ${b.length} (${JSON.stringify(a[a.length - 1]).slice(0, 120)} vs ${JSON.stringify(b[b.length - 1]).slice(0, 120)})`;
    }
    for (let i = 0; i < a.length; i++) {
      const d = firstDiff(a[i], b[i], `${path}/${i}`);
      if (d) return d;
    }
    return null;
  }
  if (a && typeof a === 'object') {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const key of keys) {
      if (!(key in a)) return `${path}/${key}: missing in archive`;
      if (!(key in b)) return `${path}/${key}: missing in port`;
      const d = firstDiff(a[key], b[key], `${path}/${key}`);
      if (d) return d;
    }
    return null;
  }
  return a === b ? null : `${path}: ${JSON.stringify(a).slice(0, 100)} != ${JSON.stringify(b).slice(0, 100)}`;
}

const archiveServer = await serve(TRAUT, 8271);
const portServer = await serve(DIST, 8272);

let failed = 0;
try {
  for (const [stem, slug] of routes) {
    const name = slug || 'index';
    const archive = await snapshot(`http://127.0.0.1:8271/${encodeURI(stem)}.html`);
    const port = await snapshot(`http://127.0.0.1:8272/${slug ? slug + '/' : ''}`);
    const diff = firstDiff(archive.tree, port.tree);
    const counts =
      `framedImage ${archive.counts['.framedImage']}/${port.counts['.framedImage']}` +
      `  img ${archive.counts.img}/${port.counts.img}` +
      `  height ${archive.height}/${port.height}`;
    const ok = !diff && archive.height === port.height;
    if (!ok) failed++;
    console.log(`${name.padEnd(24)} ${ok ? 'ok  ' : 'DIFF'}  ${counts}`);
    if (diff) console.log(`    ${diff}`);
    if (port.errors.length) console.log(`    port console: ${port.errors.join(' | ')}`);
    if (archive.errors.length) console.log(`    archive console: ${archive.errors.join(' | ')}`);
  }
} finally {
  archiveServer.close();
  portServer.close();
  ws.close();
  proc.kill();
}

console.log(`\nruntime DOM identical: ${routes.length - failed}/${routes.length}`);
process.exit(failed ? 1 : 0);
