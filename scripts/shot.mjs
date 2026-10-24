#!/usr/bin/env node
/**
 * Full-page screenshot of a URL, as a PNG file.
 *
 *   node scripts/shot.mjs <url> <out.png> [waitMs]
 *
 * Chromium's `--screenshot` flag only captures the viewport, which silently
 * limited the pixel comparison to the top 1400 px of pages that are 2900 px
 * tall. This drives the DevTools protocol instead and clips to the document's
 * real content size, so the whole page is compared.
 */
import { execSync, spawn } from 'node:child_process';
import { writeFile } from 'node:fs/promises';

const [url, out, waitMs = '2600'] = process.argv.slice(2);
if (!url || !out) {
  console.error('usage: node scripts/shot.mjs <url> <out.png> [waitMs]');
  process.exit(2);
}

// Watchdog: the wait budget plus room for Chromium to start, navigate and paint.
const SHOT_TIMEOUT_MS = Number(process.env.SHOT_TIMEOUT_MS ?? Number(waitMs) + 90_000);

const chrome =
  process.env.CHROME ??
  execSync('ls -d ~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell 2>/dev/null | tail -1', {
    shell: '/bin/sh',
  })
    .toString()
    .trim();
if (!chrome) throw new Error('no Chromium found; set $CHROME');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const port = 9300 + Math.floor(Math.random() * 400);
const proc = spawn(chrome, [
  '--headless',
  '--disable-gpu',
  '--hide-scrollbars',
  `--remote-debugging-port=${port}`,
  '--window-size=800,1400',
  'about:blank',
]);

// A Chromium that stops answering would otherwise hang the caller forever (a
// whole pixel run sat on one page overnight). Give up, kill it, fail loudly.
const watchdog = setTimeout(() => {
  console.error(`shot: ${url} did not finish within ${SHOT_TIMEOUT_MS} ms`);
  proc.kill('SIGKILL');
  process.exit(1);
}, SHOT_TIMEOUT_MS);

async function endpoint() {
  for (let i = 0; i < 100; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`);
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
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
});

function send(method, params = {}, sessionId) {
  const msgId = ++id;
  ws.send(JSON.stringify({ id: msgId, method, params, sessionId }));
  return new Promise((r) => pending.set(msgId, r));
}

try {
  const { result: target } = await send('Target.createTarget', { url: 'about:blank' });
  const { result: attached } = await send('Target.attachToTarget', { targetId: target.targetId, flatten: true });
  const { sessionId } = attached;
  await send('Page.enable', {}, sessionId);
  await send('Page.navigate', { url }, sessionId);
  await sleep(Number(waitMs));

  const { result: metrics } = await send('Page.getLayoutMetrics', {}, sessionId);
  const size = metrics.cssContentSize ?? metrics.contentSize;
  const { result: shot } = await send(
    'Page.captureScreenshot',
    {
      format: 'png',
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: Math.ceil(size.width), height: Math.ceil(size.height), scale: 1 },
    },
    sessionId,
  );
  await writeFile(out, Buffer.from(shot.data, 'base64'));
} finally {
  clearTimeout(watchdog);
  ws.close();
  proc.kill();
}
