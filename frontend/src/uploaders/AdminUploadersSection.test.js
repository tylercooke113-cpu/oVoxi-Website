/**
 * Brief 28 D6: admin Uploaders tab: authorizations list and "Act for an artist".
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

const mockAdminList = jest.fn();
const mockArtists = jest.fn();
jest.mock('./api', () => {
  const actual = jest.requireActual('./api');
  return { ...actual, uploadersApi: { adminList: (...a) => mockAdminList(...a) },
    uploaderApi: { artists: (...a) => mockArtists(...a) } };
});
jest.mock('../sync/api', () => ({ API: 'x', authed: async () => ({}), errorMessage: (e, f) => f }));
jest.mock('react-router-dom', () => ({ Link: ({ to, children, ...p }) => <a href={to} {...p}>{children}</a> }), { virtual: true });

import AdminUploadersSection from './AdminUploadersSection';

global.IS_REACT_ACT_ENVIRONMENT = true;
const ROWS = [
  { id: 'a1', kind: 'person', artist_name: 'Jane Rivers', uploader_name: 'Sam Ortiz', uploader_email: 'sam@x.com',
    uploader_role: 'Engineer', uses: ['sync', 'ai_training'], status: 'active', created_at: '2026-10-28T00:00:00Z' },
  { id: 'a2', kind: 'ovoxi', artist_name: 'Kofi Mensah', uploader_name: null, uses: ['ai_training'], status: 'active', created_at: '2026-10-26T00:00:00Z' },
];

let c;
async function render() {
  c = document.createElement('div'); document.body.appendChild(c);
  await act(async () => { createRoot(c).render(<AdminUploadersSection getToken={async () => 't'} />); });
}
const set = async (el, v) => {
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
  await act(async () => { el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); });
};

beforeEach(() => {
  document.body.innerHTML = '';
  mockAdminList.mockReset().mockResolvedValue(ROWS);
  mockArtists.mockReset().mockResolvedValue([
    { artist_user_id: 'a_kofi', artist_name: 'Kofi Mensah', uses: ['ai_training'], is_ovoxi: true },
    { artist_user_id: 'a_jane', artist_name: 'Jane Rivers', uses: ['sync'], is_ovoxi: false },   // admin's own person auth
  ]);
});

test('lists every authorization and filters by type and search', async () => {
  await render();
  expect(c.querySelector('[data-testid="admin-auth-a1"]').textContent).toContain('Sam Ortiz');
  expect(c.querySelector('[data-testid="admin-auth-a2"]').textContent).toContain('OVOXI, Inc.');
  await set(c.querySelector('[aria-label="Uploader type"]'), 'ovoxi');
  expect(c.querySelector('[data-testid="admin-auth-a1"]')).toBeNull();
  await set(c.querySelector('[aria-label="Uploader type"]'), '');
  await set(c.querySelector('[aria-label="Search"]'), 'sam');
  expect(c.querySelector('[data-testid="admin-auth-a2"]')).toBeNull();
  expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
});

test('status filter goes to the server', async () => {
  await render();
  await set(c.querySelector('[aria-label="Status"]'), 'revoked');
  expect(mockAdminList).toHaveBeenLastCalledWith(expect.any(Function), { status: 'revoked' });
});

test('act for: only OVOXI-authorized artists; links open their Vault and Upload', async () => {
  await render();
  const opts = [...c.querySelectorAll('[aria-label="Acting for"] option')].map((o) => o.value);
  expect(opts).toEqual(['', 'a_kofi']);
  await set(c.querySelector('[aria-label="Acting for"]'), 'a_kofi');
  const hrefs = [...c.querySelectorAll('[data-testid="admin-act-for-summary"] a')].map((a) => a.getAttribute('href'));
  expect(hrefs).toEqual(['/vault?for=a_kofi', '/upload?for=a_kofi']);
});
