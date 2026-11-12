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
jest.mock('axios', () => ({ post: jest.fn(() => Promise.resolve({ data: {} })) }));
import axios from 'axios';

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

const setValue = (el, value) => {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value').set;
  setter.call(el, value);
  el.dispatchEvent(new Event('input', { bubbles: true }));
};
const chip = (c, label) => [...c.querySelectorAll('label')].find((l) => l.textContent.trim() === label).querySelector('input');
const field = (c, label) => [...c.querySelectorAll('label')].find((l) => l.textContent.trim().startsWith(label)).querySelector('input');

test('/artists: network copy, apply and how-it-works anchors, sign-in block', async () => {
  const c = await render(<ArtistsPage />);
  expect(c.textContent).toContain('Record music for AI labs.');
  expect(href(c, 'artists-apply')).toBe('#apply');
  expect(href(c, 'artists-how')).toBe('#how');
  expect(c.querySelector('#apply')).not.toBeNull();
  expect(c.querySelector('#how')).not.toBeNull();
  expect(href(c, 'artists-signin')).toBe('/login');
  expect(href(c, 'artists-signup')).toBe('/signup');
  expect(c.textContent).toContain('Sync stays non-exclusive.');
});

test('/artists: copy guard (no old marketplace, no pay, Plan 29 rules)', async () => {
  const c = await render(<ArtistsPage />);
  const t = c.textContent;
  expect(t).not.toMatch(/get paid|paid monthly|wallet|earn/i);
  expect(t).not.toMatch(/browse the catalog|get early access|talk to sales/i);
  expect(t).not.toMatch(/only place your chosen songs are licensed for sync/i);
  expect(t).not.toMatch(/—/);
  expect(t).not.toMatch(/\d+\s?%/);
  expect(t).not.toMatch(/sample pack/i);
  expect(t).not.toMatch(/First Class|Quad|Platinum Sound|Penthouse|Smash|Bakery|Paramount|The Kitchen|Chalice/);
});

test('/artists: empty form shows an error and sends nothing', async () => {
  axios.post.mockClear();
  const c = await render(<ArtistsPage />);
  await act(async () => { c.querySelector('[data-testid="artists-apply-submit"]').click(); });
  expect(c.querySelector('[data-testid="artists-apply-error"]').textContent).toContain('fields marked required');
  expect(axios.post).not.toHaveBeenCalled();
});

test('/artists: a valid application posts to /api/contact as interest network', async () => {
  axios.post.mockClear();
  const c = await render(<ArtistsPage />);
  await act(async () => {
    setValue(field(c, 'Your name'), 'Jane Doe');
    setValue(field(c, 'Email'), 'jane@example.com');
    setValue(field(c, 'City'), 'Hartford, CT');
    chip(c, 'Producer').click();
    chip(c, 'R&B').click();
  });
  await act(async () => { c.querySelector('[data-testid="artists-apply-submit"]').click(); });
  expect(axios.post).toHaveBeenCalledTimes(1);
  const [url, body] = axios.post.mock.calls[0];
  expect(url).toMatch(/\/api\/contact$/);
  expect(body.interest).toBe('network');
  expect(body.name).toBe('Jane Doe');
  expect(body.message).toContain('Roles: Producer');
  expect(body.message).toContain('Genres: R&B');
  expect(body.message).toContain('City: Hartford, CT');
  expect(c.querySelector('[data-testid="artists-apply-success"]').textContent).toContain('Thanks, Jane.');
});
