import { safeNext } from './safeNext';

describe('safeNext (Brief 20 B3)', () => {
  test.each([
    ['/account', '/account'],
    ['/vault', '/vault'],
    ['/sync', '/sync'],
    ['/sync/track/abc', '/sync/track/abc'],
    ['/pricing', '/pricing'],
    ['/pricing?subscribe=pro&interval=m', '/pricing?subscribe=pro&interval=m'],
  ])('allows %s', (input, expected) => expect(safeNext(input)).toBe(expected));

  test.each([
    ['//evil.com'],
    ['/\\evil.com'],
    ['https://evil.com'],
    ['javascript:alert(1)'],
    ['/unknown'],
    [null],
    [undefined],
  ])('falls back %s to /vault', (input) => expect(safeNext(input)).toBe('/vault'));
});
