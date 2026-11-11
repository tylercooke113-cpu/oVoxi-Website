// Where the landing pages send each visitor (Tyler, Oct 27; Nov 11 Custom Datasets).
export const LINKS = {
  request: '/request',                      // every "Request data" (Brief 31)
  how: '/#how',                             // header "How it works"
  join: '/signup',                          // every "Join as an artist"
  artists: '/artists',                      // "For artists" and "Join the network"
  catalog: '/catalog',                      // when the catalog is switched on
  earlyAccess: '/contact?interest=buyer',   // "Browse the catalog" until then
  ai: '/contact?interest=ai_company',       // AI teams (kept for old links)
  pricing: '/pricing',
  signIn: '/login',
};

// The buyer button: the catalog when it is on, otherwise an early-access request.
export const buyerCta = (catalogVisible) => (catalogVisible
  ? { to: LINKS.catalog, label: 'Browse the catalog' }
  : { to: LINKS.earlyAccess, label: 'Get early access' });
