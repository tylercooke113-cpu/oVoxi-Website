// Cached site flags from /api/sync/pricing, so links do not flash on the next load.
// Cached separately for signed-in and signed-out visits: an admin's "catalog visible"
// must never carry into a signed-out session after logout.
const key = (name, signedIn) => `ovoxi_${name}_${signedIn ? 'in' : 'out'}`;

export const readFlag = (name, signedIn) => {
  try { return sessionStorage.getItem(key(name, signedIn)) === '1'; } catch { return false; }
};

export const writeFlag = (name, signedIn, on) => {
  try { sessionStorage.setItem(key(name, signedIn), on ? '1' : '0'); } catch { /* ignore */ }
};
