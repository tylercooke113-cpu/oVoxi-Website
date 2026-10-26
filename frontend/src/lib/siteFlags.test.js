import { readFlag, writeFlag } from './siteFlags';

beforeEach(() => sessionStorage.clear());

test('flags cached while signed in never show for a signed-out visit', () => {
  writeFlag('library_visible', true, true);          // admin session: catalog visible
  expect(readFlag('library_visible', true)).toBe(true);
  expect(readFlag('library_visible', false)).toBe(false);   // after logout: not visible
});

test('signed-out flags are cached on their own', () => {
  writeFlag('pricing_visible', false, true);
  expect(readFlag('pricing_visible', false)).toBe(true);
  expect(readFlag('pricing_visible', true)).toBe(false);
});
