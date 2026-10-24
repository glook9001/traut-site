#!/usr/bin/env node
/**
 * Deminify the archive's JavaScript with esbuild's printer.
 *
 * iWeb shipped its scripts minified onto enormous lines: WidgetCommon.js is
 * 36 KB in 422 lines, iWebSite.js 146 KB in 1024, and the per-page scripts are
 * single 2 KB statements. Nothing about that is part of the site -- the bytes
 * are just the 2008 build output. This writes the same programs, printed by the
 * JavaScript parser Astro already bundles (esbuild), to `formatted/<archive
 * path>`; `scripts/mirror_archive.py` serves those copies instead of the
 * archive's and rewrites the `.js` references to `../formatted/…`.
 *
 * Equivalence is checked, not assumed. esbuild's printer is idempotent, so
 * `format(format(x)) === format(x)`; the only thing it drops is the leading
 * `//` banner (esbuild keeps legal comments only), which is re-attached here
 * byte for byte. `--check` re-derives every file and fails on any difference,
 * and the runtime DOM audit (`npm run audit`) runs the formatted scripts in a
 * browser and compares the result with the archive's own.
 *
 * `Scripts/iWPopUpSlideshow.js` is not a valid program in the local archive
 * copy -- it lost the first half of `checkBrowser()`, leaving
 * `function checkBrowser(){return true;}else if(…)` -- so it is left exactly as
 * the archive has it. It is the slideshow popup's script, and the popup is
 * broken in the archive itself; nothing in the port loads the file, and printing
 * it would mean inventing the missing code. Every other script is formatted.
 *
 *   node scripts/format_js.mjs           # write formatted/
 *   node scripts/format_js.mjs --check   # fail if formatted/ is not current
 */
import { transformSync } from 'esbuild';
import { access, readFile, readdir, mkdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const TRAUT = join(ROOT, '..', 'Traut.com');
const FORMATTED = join(ROOT, 'formatted');

/** Archive scripts that are not valid programs, and so are left untouched. */
const UNPARSEABLE = new Set(['Scripts/iWPopUpSlideshow.js']);

/** The banner every iWeb script starts with: consecutive `//` lines. */
const HEADER = /^((?:[ \t]*\/\/[^\n]*(?:\n|$))+)/;

/**
 * One file: keep the banner, print the rest.
 *
 * `loader: 'js'` means esbuild parses the script as a classic script (no ESM
 * conversion, no bundling, no downlevelling -- the default target is esnext), so
 * the output is the same program with the same semantics.
 */
function formatJs(source, ref) {
  const header = HEADER.exec(source)?.[1] ?? '';
  const body = source.slice(header.length);
  const { code } = transformSync(body, {
    loader: 'js',
    legalComments: 'inline',
    charset: 'utf8',
    sourcefile: ref,
  });
  return header ? `${header}\n${code}` : code;
}

/** Whether a path exists (the check needs it for the unparseable skip). */
const exists = (path) => access(path).then(() => true, () => false);

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(path)));
    else if (entry.name.endsWith('.js')) out.push(path);
  }
  return out;
}

const sources = await walk(TRAUT);
const refs = sources.map((path) => relative(TRAUT, path).split(sep).join('/')).sort();

const check = process.argv.includes('--check');
const stale = [];
let written = 0;
let failed = 0;

if (!check) await rm(FORMATTED, { recursive: true, force: true });

for (const ref of refs) {
  // Not a program: leave the archive's bytes alone rather than invent them.
  if (UNPARSEABLE.has(ref)) {
    if (check && (await exists(join(FORMATTED, ref)))) {
      stale.push(`${ref}: is not parseable, so it must not be in formatted/`);
    }
    continue;
  }

  const original = await readFile(join(TRAUT, ref), 'utf8');
  let output;
  try {
    output = formatJs(original, ref);
    // The printer must be idempotent: reprinting its own output cannot change it.
    if (formatJs(output, ref) !== output) throw new Error("esbuild's printer is not idempotent");
  } catch (error) {
    console.error(`!! ${ref}: ${String(error.message ?? error).split('\n')[0]}`);
    failed++;
    continue;
  }

  const dest = join(FORMATTED, ref);
  if (check) {
    let current = null;
    try {
      current = await readFile(dest, 'utf8');
    } catch {
      stale.push(`${ref}: missing from formatted/`);
      continue;
    }
    if (current !== output) stale.push(`${ref}: formatted/ is stale`);
  } else {
    await mkdir(dirname(dest), { recursive: true });
    await writeFile(dest, output);
    written++;
  }
}

const formatted = refs.filter((ref) => !UNPARSEABLE.has(ref));

if (check) {
  // Nothing extra: formatted/ is exactly the archive's parseable .js files.
  for (const path of await walk(FORMATTED).catch(() => [])) {
    const ref = relative(FORMATTED, path).split(sep).join('/');
    if (!formatted.includes(ref)) stale.push(`${ref}: not a formatted archive script`);
  }
  for (const ref of UNPARSEABLE) {
    if (!refs.includes(ref)) stale.push(`${ref}: listed as unparseable but not in the archive`);
  }
  if (stale.length || failed) {
    for (const line of stale) console.error(`  ${line}`);
    console.error(`\n${stale.length + failed} problem(s); run \`npm run format\``);
    process.exit(1);
  }
  console.log(
    `ok formatted: ${formatted.length} archive scripts deminified, byte-current` +
      ` (${UNPARSEABLE.size} unparseable, left as archived)`,
  );
} else {
  console.log(
    `formatted: ${written} archive scripts -> ${relative(ROOT, FORMATTED)}/` +
      ` (skipped ${UNPARSEABLE.size}: not valid programs)`,
  );
  if (failed) process.exit(1);
}
