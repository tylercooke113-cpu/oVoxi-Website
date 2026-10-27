// Where the landing pages send each visitor (Tyler, Oct 27).
export const LINKS = {
  join: '/signup',                          // every "Join as an artist"
  artists: '/artists',                      // "For artists" and "How it works"
  catalog: '/catalog',                      // when the catalog is switched on
  earlyAccess: '/contact?interest=buyer',   // "Browse the catalog" until then
  ai: '/contact?interest=ai_company',       // AI teams
  pricing: '/pricing',
  signIn: '/login',
};

// The buyer button: the catalog when it is on, otherwise an early-access request.
export const buyerCta = (catalogVisible) => (catalogVisible
  ? { to: LINKS.catalog, label: 'Browse the catalog' }
  : { to: LINKS.earlyAccess, label: 'Get early access' });
