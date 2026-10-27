/**
 * Brief 23 C1: the header renders the right links per viewer. react-dom + act in jsdom.
 * Clerk, the router, the pricing fetch and the buyer-access modal are mocked.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

let mockUser;
let mockSignedIn;
let mockPricing;

jest.mock('@clerk/clerk-react', () => ({
  useUser: () => ({ isSignedIn: mockSignedIn, user: mockUser }),
  useAuth: () => ({ getToken: async () => 't', isSignedIn: mockSignedIn, isLoaded: true }),
}));
jest.mock('react-router-dom', () => ({
  Link: ({ to, children, ...p }) => <a href={to} {...p}>{children}</a>,
  useNavigate: () => () => {},
}), { virtual: true });
jest.mock('lucide-react', () => ({ Menu: () => null, X: () => null }));
jest.mock('./BuyerAccessModal', () => () => null);
jest.mock('../sync/api', () => ({ publicApi: { pricing: (...a) => mockPricing(...a) } }));

import { Header } from './Header';

global.IS_REACT_ACT_ENVIRONMENT = true;

async function renderHeader() {
  const container = document.createElement('div');
  document.body.appendChild(container);
  await act(async () => { createRoot(container).render(<Header />); });
  return container;
}

const ids = (c) => [...c.querySelectorAll('[data-testid^="nav-"], [data-testid^="header-"]')]
  .map((e) => e.getAttribute('data-testid'));

const pub = (role, buyer) => ({ ...(role ? { role } : {}), ...(buyer ? { buyer } : {}) });
const user = ({ role, buyer, accountType } = {}) =>
  ({ publicMetadata: pub(role, buyer), unsafeMetadata: accountType ? { account_type: accountType } : {} });

beforeEach(() => {
  sessionStorage.clear();
  mockUser = null;
  mockSignedIn = false;
  mockPricing = jest.fn().mockResolvedValue({ visible: true, library_visible: true });
});

test('signed out (Oct 27 landing): Catalog, For artists, For AI teams, Pricing, Sign in', async () => {
  const c = await renderHeader();
  const got = ids(c);
  expect(got).toEqual(expect.arrayContaining(
    ['nav-browse', 'nav-pricing', 'header-artist-cta', 'header-partnership-cta', 'nav-signin']));
  expect(got).not.toContain('nav-contact');
  expect(got).not.toContain('nav-vault');
  expect(got).not.toContain('nav-account');
  const href = (id) => c.querySelector(`[data-testid="${id}"]`).getAttribute('href');
  expect(href('header-artist-cta')).toBe('/artists');
  expect(href('header-partnership-cta')).toBe('/contact?interest=ai_company');
  expect(href('nav-signin')).toBe('/login');
  expect(href('nav-browse')).toBe('/catalog');
});

test('catalog hidden: signed-out sees no Browse button', async () => {
  mockPricing = jest.fn().mockResolvedValue({ visible: false, library_visible: false });
  const got = ids(await renderHeader());
  expect(got).not.toContain('nav-browse');
  expect(got).toEqual(expect.arrayContaining(['header-artist-cta', 'header-partnership-cta']));
});

test('artist without buyer access: My Vault + Browse (prompt), no catalog/account/pricing', async () => {
  mockSignedIn = true; mockUser = user({ role: 'artist' });
  const got = ids(await renderHeader());
  expect(got).toEqual(expect.arrayContaining(['nav-vault', 'nav-browse', 'nav-contact']));
  expect(got).not.toContain('nav-catalog');
  expect(got).not.toContain('nav-account');
  expect(got).not.toContain('nav-pricing');
});

test('artist with buyer access: My Vault, OVOXI Catalog, Pricing, My account', async () => {
  mockSignedIn = true; mockUser = user({ role: 'artist', buyer: true });
  const got = ids(await renderHeader());
  expect(got).toEqual(expect.arrayContaining(['nav-vault', 'nav-catalog', 'nav-pricing', 'nav-account']));
  expect(got).not.toContain('nav-browse');
});

test('pure buyer: OVOXI Catalog, Pricing, My account; no Vault', async () => {
  mockSignedIn = true; mockUser = user({ accountType: 'buyer' });
  const got = ids(await renderHeader());
  expect(got).toEqual(expect.arrayContaining(['nav-catalog', 'nav-pricing', 'nav-account']));
  expect(got).not.toContain('nav-vault');
});

test('admin: Vault, Catalog, Pricing, account', async () => {
  mockSignedIn = true; mockUser = user({ role: 'admin' });
  const got = ids(await renderHeader());
  expect(got).toEqual(expect.arrayContaining(['nav-vault', 'nav-catalog', 'nav-pricing', 'nav-account']));
});
