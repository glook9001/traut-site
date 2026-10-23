#!/usr/bin/env node
/**
 * Evaluate a JS expression in a page rendered by headless Chromium and print
 * the result as JSON. Used to explain pixel diffs between the archive and the
 * port (element geometry, computed styles, console errors).
 *
 *   node scripts/probe_layout.mjs <url> "<js expression>" [waitMs]
 *
 * The expression runs after the page's load handlers and iWeb's own scripts,
 * so `document.querySelector('#id4')` and friends are ready.
 */
import { execSync, spawn } from 'node:child_process';

const [url, expression = 'document.title', waitMs = '2500'] = process.argv.slice(2);
const chrome = process.env.CHROME ?? findChrome();

function findChrome() {
  const found = execSync(
    'ls -d ~/.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell 2>/dev/null | tail -1',
    { shell: '/bin/sh' },
  )
    .toString()
    .trim();
  if (!found) throw new Error('no Chromium found; set $CHROME');
  return found;
}

const port = 9400 + Math.floor(Math.random() * 400);
const proc = spawn(chrome, [
  '--headless',
  '--disable-gpu',
  '--hide-scrollbars',
  `--remote-debugging-port=${port}`,
  '--window-size=800,1400',
  'about:blank',
]);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

const wsUrl = await endpoint();
const ws = new WebSocket(wsUrl);
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

const { result: target } = await send('Target.createTarget', { url: 'about:blank' });
const { result: attached } = await send('Target.attachToTarget', { targetId: target.targetId, flatten: true });
const sessionId = attached.sessionId;

const logs = [];
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.method === 'Runtime.consoleAPICalled') {
    logs.push(msg.params.args.map((a) => a.value ?? a.description).join(' '));
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    logs.push('EXCEPTION ' + (msg.params.exceptionDetails.exception?.description ?? ''));
  }
});

await send('Runtime.enable', {}, sessionId);
await send('Page.enable', {}, sessionId);
await send('Page.navigate', { url }, sessionId);
await sleep(Number(waitMs));

const { result } = await send(
  'Runtime.evaluate',
  { expression, returnByValue: true, awaitPromise: true },
  sessionId,
);

console.log(JSON.stringify(result.result?.value ?? result, null, 2));
if (logs.length) console.error('--- console ---\n' + logs.join('\n'));

ws.close();
proc.kill();
