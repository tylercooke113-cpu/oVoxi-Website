/**
 * Oct 27 landing pages: every button goes where Tyler asked.
 * Join as an artist -> /signup; For artists / How it works -> /artists;
 * the buyer button -> /catalog when the catalog is on, else "Get early access".
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

let mockLibrary = false;
jest.mock('@clerk/clerk-react', () => ({ useAuth: () => ({ getToken: async () => 't', isSignedIn: false, isLoaded: true }) }));
jest.mock('react-router-dom', () => ({
  Link: ({ to, children, ...p }) => <a href={to} {...p}>{children}</a>,
  useLocation: () => ({ hash: '' }),
}), { virtual: true });
jest.mock('../sync/api', () => ({ publicApi: { pricing: async () => ({ visible: true, library_visible: mockLibrary }) } }));

import HomePage from '../pages/HomePage';
import ArtistsPage from '../pages/ArtistsPage';

global.IS_REACT_ACT_ENVIRONMENT = true;

async function render(ui) {
  const c = document.createElement('div');
  document.body.appendChild(c);
  await act(async () => { createRoot(c).render(ui); });
  return c;
}
const byText = (c, text) => [...c.querySelectorAll('a')].filter((a) => a.textContent.trim() === text);
const href = (c, id) => c.querySelector(`[data-testid="${id}"]`).getAttribute('href');

beforeEach(() => { sessionStorage.clear(); mockLibrary = false; });

test('home: Custom Datasets hero, every Request data goes to /request', async () => {
  const c = await render(<HomePage />);
  expect(c.textContent).toContain("The music data your model needs doesn't exist yet. We record it.");
  const req = byText(c, 'Request data');
  expect(req.length).toBeGreaterThanOrEqual(3);
  req.forEach((a) => expect(a.getAttribute('href')).toBe('/request'));
  expect(href(c, 'home-how')).toBe('#how');
  expect(c.querySelector('#how')).not.toBeNull();
  expect(href(c, 'home-artists')).toBe('/artists');
});

test('home: no old marketplace doors', async () => {
  const c = await render(<HomePage />);
  expect(c.querySelector('[data-testid="door-buyer"]')).toBeNull();
  expect(c.querySelector('[data-testid="door-artist"]')).toBeNull();
  expect(byText(c, 'Browse the catalog')).toHaveLength(0);
  expect(byText(c, 'Get early access')).toHaveLength(0);
});

test('home: copy guard (Plan 29 rules)', async () => {
  const c = await render(<HomePage />);
  const t = c.textContent;
  expect(t).not.toMatch(/sample pack/i);
  expect(t).not.toMatch(/—/);                        // no em dashes
  expect(t).not.toMatch(/deposit|\$\d|business days/i);   // no terms, prices or reply times
  expect(t).not.toMatch(/1,127|1127|2,300|\b26 artists/); // no catalog counts
  expect(t).not.toMatch(/First Class|Quad|Platinum Sound|Penthouse|Smash|Bakery|Paramount|The Kitchen|Chalice/); // no studio names
  expect(t).not.toMatch(/5-stem|stem separation/i);
});

test('/artists: Join goes to sign-up, FAQ present', async () => {
  const c = await render(<ArtistsPage />);
  byText(c, 'Join as an artist').forEach((a) => expect(a.getAttribute('href')).toBe('/signup'));
  expect(href(c, 'artists-join')).toBe('/signup');
  expect(c.textContent).toContain('Do I keep my rights?');
  expect(byText(c, 'Get early access')[0].getAttribute('href')).toBe('/contact?interest=buyer');
});
