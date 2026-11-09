/**
 * Brief 28 Part D2: /authorize/:token. react-dom + act in jsdom; Clerk and the API mocked.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
// react-router-dom v7 is ESM-only; jest's CJS resolver can't load it, so mock virtually.
jest.mock('react-router-dom', () => ({
  useParams: () => ({ token: 'tok_123' }),
  Link: ({ to, children, ...p }) => <a href={to} {...p}>{children}</a>,
}), { virtual: true });

let mockClerk = { isLoaded: true, isSignedIn: true };
const mockGetToken = async () => 't';
jest.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ ...mockClerk, getToken: mockGetToken }),
  SignOutButton: ({ children }) => children,
}));
const mockGet = jest.fn();
const mockSign = jest.fn();
const mockDecline = jest.fn();
jest.mock('../uploaders/api', () => {
  const actual = jest.requireActual('../uploaders/api');
  return { ...actual, authorizeApi: { get: (...a) => mockGet(...a), sign: (...a) => mockSign(...a), decline: (...a) => mockDecline(...a) } };
});
jest.mock('lucide-react', () => ({ Loader2: () => null, CheckCircle2: () => null, AlertCircle: () => null }));
jest.mock('../sync/api', () => ({ API: 'x', authed: async () => ({}),
  errorMessage: (e, f) => e?.response?.data?.detail || e?.message || f }));
jest.mock('../agreement/AgreementDoc', () => () => <div data-testid="doc">doc</div>);

import AuthorizePage from './AuthorizePage';

global.IS_REACT_ACT_ENVIRONMENT = true;

const INVITE = { artist_name: 'Jane Rivers', uploader_name: 'Sam Ortiz', uploader_email: 'sam@x.com',
  uploader_role: 'Engineer', uses: ['sync', 'ai_training'], version: 'upload_auth_v1', blocks: [], text_sha256: 'b'.repeat(64) };
const httpErr = (status, detail) => Object.assign(new Error('x'), { response: { status, data: { detail } } });

let c;
async function render() {
  c = document.createElement('div');
  document.body.appendChild(c);
  await act(async () => {
    createRoot(c).render(<AuthorizePage />);
  });
}
const q = (sel) => c.querySelector(sel);
const btn = (text) => [...c.querySelectorAll('button')].find((b) => b.textContent.trim() === text);
const click = async (el) => { await act(async () => { el.click(); }); };
const type = async (el, value) => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, value);
  await act(async () => { el.dispatchEvent(new Event('input', { bubbles: true })); });
};

beforeEach(() => {
  document.body.innerHTML = '';
  mockClerk = { isLoaded: true, isSignedIn: true };
  [mockGet, mockSign, mockDecline].forEach((m) => m.mockReset());
  mockGet.mockResolvedValue(INVITE);
});

test('signed out: sign-in and sign-up links come back to this page; nothing is fetched', async () => {
  mockClerk = { isLoaded: true, isSignedIn: false };
  await render();
  expect(q('[data-testid="authorize-signed-out"]')).not.toBeNull();
  const hrefs = [...c.querySelectorAll('a')].map((a) => a.getAttribute('href'));
  expect(hrefs).toEqual(['/login?next=%2Fauthorize%2Ftok_123', '/signup?as=uploader&next=%2Fauthorize%2Ftok_123']);
  expect(mockGet).not.toHaveBeenCalled();
});

test('wrong email (403) shows the server message and a switch button', async () => {
  mockGet.mockRejectedValue(httpErr(403, 'Sign in with sam@x.com to accept.'));
  await render();
  expect(q('[data-testid="authorize-wrong"]').textContent).toContain('Sign in with sam@x.com to accept.');
  expect(btn('Sign out and switch')).toBeDefined();
});

test('expired or unknown link (404) and already handled (409)', async () => {
  mockGet.mockRejectedValue(httpErr(404, 'This link has expired. Ask the artist to resend it.'));
  await render();
  expect(q('[data-testid="authorize-invalid"]').textContent).toContain('expired');
  mockGet.mockRejectedValue(httpErr(409, { status: 'revoked' }));
  await render();
  expect(q('[data-testid="authorize-handled"]').textContent).toContain('Invitation cancelled');
});

test('ready: sign needs both boxes and the exact invited name', async () => {
  mockSign.mockResolvedValue({ status: 'active' });
  await render();
  const page = q('[data-testid="authorize-ready"]');
  expect(page.textContent).toContain('Jane Rivers wants you to upload songs for them');
  expect(page.textContent).toContain('Sync and AI training');
  expect(page.textContent).not.toMatch(/\bpay/i);           // Decision 12
  expect(page.textContent).not.toMatch(/[\u2013\u2014]/);
  const signBtn = btn('Sign');
  await click(q('[data-testid="adult"]'));
  await click(q('[data-testid="agree"]'));
  await type(q('#auth-sig'), 'Sam O');
  expect(signBtn.disabled).toBe(true);
  await type(q('#auth-sig'), ' sam  ortiz ');
  expect(signBtn.disabled).toBe(false);
  await click(signBtn);
  expect(mockSign).toHaveBeenCalledWith(expect.any(Function), 'tok_123',
    { typed_signature: 'sam ortiz', adult_confirmed: true, text_sha256: 'b'.repeat(64) });
  expect(q('[data-testid="authorize-signed"]').textContent).toContain('You can now upload for Jane Rivers');
});

test('decline sends the optional reason', async () => {
  mockDecline.mockResolvedValue({ status: 'declined' });
  await render();
  await click(btn('Decline'));
  await type(q('#auth-decline'), 'Not my client');
  await click(q('[data-testid="confirm-decline"]'));
  expect(mockDecline).toHaveBeenCalledWith(expect.any(Function), 'tok_123', 'Not my client');
  expect(q('[data-testid="authorize-declined"]')).not.toBeNull();
});
