/**
 * Astro always emits `<!DOCTYPE html>` for a page, replacing whatever doctype
 * the template declared. That matters here: iWeb's XHTML 1.0 Transitional
 * doctype puts Chromium in **almost standards mode**, where the descender of a
 * line box holding an inline-block image is not added. Under `<!DOCTYPE html>`
 * (full standards mode) every photo block grows ~3px, iWeb's own line-height
 * fitter kicks in, and the page drifts from the archive by a few pixels.
 *
 * So after the build, put the archive's doctype back. It is the one piece of
 * the original markup Astro will not let a template control.
 */
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DOCTYPE =
  '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">';

/** @param {string} dir */
async function* htmlFiles(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* htmlFiles(path);
    else if (entry.name.endsWith('.html')) yield path;
  }
}

export default function iwebDoctype() {
  return {
    name: 'iweb-doctype',
    hooks: {
      'astro:build:done': async ({ dir, logger }) => {
        const root = fileURLToPath(dir);
        let patched = 0;
        for await (const file of htmlFiles(root)) {
          const html = await readFile(file, 'utf8');
          if (!html.startsWith('<!DOCTYPE html>')) continue;
          await writeFile(file, DOCTYPE + html.slice('<!DOCTYPE html>'.length));
          patched += 1;
        }
        logger.info(`restored the iWeb doctype on ${patched} pages`);
      },
    },
  };
}
