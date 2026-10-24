// The archive expressed its layout as inline styles. The port keeps only the
// numbers, as an ordered map of declarations (`{ height: '40px', left: '19px' }`),
// and turns them back into a style attribute in one place.
//
// They cannot move into a stylesheet: iWeb's own runtime reads the geometry back
// off the DOM (`spacer.style.height` in IWSetSpacerHeight(),
// `textBlock.style.height` in adjustLineHeightIfTooBig(), `photogrid.style.top`
// in the media grid). The inline attribute is the runtime's input, not just
// presentation.
import type { Box } from './types';

/** `{ height: '0px', 'line-height': '0px' }` -> `"height: 0px; line-height: 0px;"` */
export function styleOf(box: Box | undefined): string | undefined {
  if (!box) return undefined;
  const declarations = Object.entries(box).filter(([, value]) => value !== '');
  if (!declarations.length) return undefined;
  return declarations.map(([name, value]) => `${name}: ${value};`).join(' ');
}
