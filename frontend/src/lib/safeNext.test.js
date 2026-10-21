import { safeNext } from './safeNext';

describe('safeNext (Brief 20 B3)', () => {
  test.each([
    ['/account', '/account'],
    ['/vault', '/vault'],
    ['/sync', '/sync'],
    ['/sync/track/abc', '/sync/track/abc'],
    ['/sync?sort=newest', '/sync?sort=newest'],
    ['/sync/track/abc?license=t1', '/sync/track/abc?license=t1'],
    ['/artist/jane-doe', '/artist/jane-doe'],
    ['/artist/jane-doe?license=t1', '/artist/jane-doe?license=t1'],
    ['/pricing', '/pricing'],
    ['/pricing?subscribe=pro&interval=m', '/pricing?subscribe=pro&interval=m'],
  ])('allows %s', (input, expected) => expect(safeNext(input)).toBe(expected));

  test.each([
    ['//evil.com'],
    ['/\\evil.com'],
    ['https://evil.com'],
    ['javascript:alert(1)'],
    ['/unknown'],
    ['/artist/Jane Doe'],
    ['/artist/'],
    ['/artistjane'],
    [null],
    [undefined],
  ])('falls back %s to /vault', (input) => expect(safeNext(input)).toBe('/vault'));
});
