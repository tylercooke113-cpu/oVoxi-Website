// Shared guard for post-auth redirect targets (Brief 20 B3). Only our own in-app
// paths are allowed; anything else falls back to /vault so a crafted `next` can
// never become an open redirect. Used by LoginPage, SignUpPage and the Pricing page.

const ALLOWED = [/^\/account$/, /^\/vault$/, /^\/sync(\/|$)/, /^\/pricing(\?|$)/];

export const safeNext = (next) => {
  if (typeof next !== 'string') return '/vault';
  // Must be a single-slash absolute path: rejects "//evil.com", "/\evil.com",
  // "https://evil.com" and "javascript:" alike.
  if (!next.startsWith('/') || next.startsWith('//') || next.includes('\\')) return '/vault';
  return ALLOWED.some((re) => re.test(next)) ? next : '/vault';
};

export default safeNext;
