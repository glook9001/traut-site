// The site's CSS, imported the Astro way: Vite resolves each file, emits it as
// a content-hashed asset and returns its URL. `?url` keeps a page's stylesheet
// out of every other page's bundle -- each route links exactly one.
import type { WidgetName } from './types';

const pageCss = import.meta.glob('../styles/pages/*.css', {
  query: '?url',
  eager: true,
  import: 'default',
}) as Record<string, string>;

const widgetCss = import.meta.glob('../styles/widgets/*.css', {
  query: '?url',
  eager: true,
  import: 'default',
}) as Record<string, string>;

/** The iWeb stylesheet for one route (src/styles/pages/<key>.css). */
export function pageStylesheet(key: string): string {
  const url = pageCss[`../styles/pages/${key}.css`];
  if (!url) throw new Error(`no stylesheet for page ${key}`);
  return url;
}

/** One of the three shared iWeb widget stylesheets. */
export function widgetStylesheet(name: WidgetName | string): string {
  const file = name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
  const url = widgetCss[`../styles/widgets/${file}.css`];
  if (!url) throw new Error(`no stylesheet for widget ${name}`);
  return url;
}
