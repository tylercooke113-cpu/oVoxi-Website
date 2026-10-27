/**
 * Oct 27 landing pages: every button goes where Tyler asked.
 * Join as an artist -> /signup; For artists / How it works -> /artists;
 * the buyer button -> /catalog when the catalog is on, else "Get early access".
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

let mockLibrary = false;
jest.mock('@clerk/clerk-react', () => ({ useAuth: () => ({ getToken: async () => 't', isSignedIn: false, isLoaded: true }) }));
jest.mock('react-router-dom', () => ({ Link: ({ to, children, ...p }) => <a href={to} {...p}>{children}</a> }), { virtual: true });
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

test('home: every Join as an artist goes to sign-up; How it works goes to /artists', async () => {
  const c = await render(<HomePage />);
  const joins = byText(c, 'Join as an artist');
  expect(joins.length).toBeGreaterThanOrEqual(3);
  joins.forEach((a) => expect(a.getAttribute('href')).toBe('/signup'));
  byText(c, 'How it works').forEach((a) => expect(a.getAttribute('href')).toBe('/artists'));
  expect(href(c, 'home-ai')).toBe('/contact?interest=ai_company');
  expect(c.textContent).toContain('Music that\'s cleared. Artists who get paid.');
});

test('home: catalog off, the I need music card asks for early access', async () => {
  const c = await render(<HomePage />);
  expect(c.querySelector('[data-testid="door-buyer"]')).not.toBeNull();
  expect(href(c, 'home-buyer')).toBe('/contact?interest=buyer');
  expect(c.querySelector('[data-testid="home-buyer"]').textContent).toContain('Get early access');
  expect(byText(c, 'Browse the catalog')).toHaveLength(0);
});

test('home: catalog on, the buyer button browses the catalog', async () => {
  mockLibrary = true;
  const c = await render(<HomePage />);
  expect(href(c, 'home-buyer')).toBe('/catalog');
  expect(c.querySelector('[data-testid="home-buyer"]').textContent).toContain('Browse the catalog');
});

test('home: no numbers section', async () => {
  const c = await render(<HomePage />);
  expect(c.textContent).not.toMatch(/\[N\]|paid to artists|cleared tracks/);
});

test('/artists: Join goes to sign-up, FAQ present', async () => {
  const c = await render(<ArtistsPage />);
  byText(c, 'Join as an artist').forEach((a) => expect(a.getAttribute('href')).toBe('/signup'));
  expect(href(c, 'artists-join')).toBe('/signup');
  expect(c.textContent).toContain('Do I keep my rights?');
  expect(byText(c, 'Get early access')[0].getAttribute('href')).toBe('/contact?interest=buyer');
});
