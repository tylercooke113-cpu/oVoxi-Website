/**
 * Brief 26: the prompt shows signed out with no choice, hides after one, and the
 * manager applies the account's choice when signed in. react-dom + act in jsdom.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

let mockSignedIn = false;
const mockPost = jest.fn();
const mockGet = jest.fn();
jest.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ isLoaded: true, isSignedIn: mockSignedIn, getToken: async () => 'tok' }),
}));
jest.mock('react-router-dom', () => ({
  Link: ({ to, children, ...p }) => <a href={to} {...p}>{children}</a>,
}), { virtual: true });
jest.mock('../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, disabled, ...p }) => (
    <input type="checkbox" checked={!!checked} disabled={disabled} onChange={(e) => onCheckedChange(e.target.checked)} {...p} />
  ),
}));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('axios', () => ({ post: (...a) => mockPost(...a), get: (...a) => mockGet(...a) }));
jest.mock('../sync/api', () => ({
  API: 'https://api.test/api',
  maybeAuthed: async () => ({ headers: { Authorization: 'Bearer tok' } }),
  errorMessage: (e) => String(e),
}));

import ConsentPrompt from './ConsentPrompt';
import ConsentManager from './ConsentManager';
import { getCurrentChoice, readVisitChoice, saveVisitChoice, setCurrentChoice } from '../lib/consent';

global.IS_REACT_ACT_ENVIRONMENT = true;

const setGpc = (on) => Object.defineProperty(navigator, 'globalPrivacyControl', { value: on, configurable: true });

async function render(ui) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => { root.render(ui); });
  return { container, root };
}
const click = async (el) => { await act(async () => { el.click(); }); };
const q = (c, id) => c.querySelector(`[data-testid="${id}"]`);

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  document.body.innerHTML = '';
  mockSignedIn = false;
  setGpc(undefined);
  mockPost.mockReset().mockResolvedValue({ data: { saved: true, choice: null } });
  mockGet.mockReset();
  setCurrentChoice(undefined);
});

const app = () => <><ConsentManager /><ConsentPrompt /></>;

test('signed out with no choice: the prompt shows with the policy copy', async () => {
  const { container } = await render(app());
  const card = q(container, 'consent-prompt');
  expect(card).not.toBeNull();
  expect(card.textContent).toBe(
    'OVOXI uses essential technologies to run the site. With your permission, we also use analytics '
    + 'and session replay to improve it. See our Data Collection Policy and Privacy Policy.'
    + 'Accept allRejectCustomize');
  expect(card.textContent).not.toContain('Your data, your choice');
  expect(card.querySelector('a[href="/data-policy"]')).not.toBeNull();
  expect(card.querySelector('a[href="/privacy"]')).not.toBeNull();
  expect(document.activeElement).toBe(card);
});

test('Reject hides the prompt, saves the visit choice and records it', async () => {
  const { container } = await render(app());
  await click(q(container, 'consent-reject'));
  expect(q(container, 'consent-prompt')).toBeNull();
  expect(readVisitChoice()).toMatchObject({ analytics: false, advertising: false });
  expect(mockPost.mock.calls[0][1]).toMatchObject({ analytics: false, advertising: false, source: 'prompt' });
});

test('a choice made earlier in the visit: no prompt', async () => {
  saveVisitChoice({ analytics: true, advertising: false });
  const { container } = await render(app());
  expect(q(container, 'consent-prompt')).toBeNull();
});

test('Customize: essential locked on, picks saved', async () => {
  const { container } = await render(app());
  await click(q(container, 'consent-customize-open'));
  expect(q(container, 'consent-essential').disabled).toBe(true);
  expect(q(container, 'consent-essential').checked).toBe(true);
  await click(q(container, 'consent-analytics'));
  await click(q(container, 'consent-save'));
  expect(readVisitChoice()).toMatchObject({ analytics: true, advertising: false });
});

test('GPC: advertising is off and locked in Customize, and Accept all keeps it off', async () => {
  setGpc(true);
  const { container } = await render(app());
  await click(q(container, 'consent-customize-open'));
  const ad = q(container, 'consent-advertising');
  expect(ad.disabled).toBe(true);
  expect(ad.checked).toBe(false);
  expect(container.textContent).toContain("Global Privacy Control is on");
  setCurrentChoice(null);
  sessionStorage.clear();
  const again = await render(<ConsentPrompt />);
  await click(q(again.container, 'consent-accept'));
  expect(readVisitChoice()).toMatchObject({ analytics: true, advertising: false });
});

test('signed in with a saved account choice: no prompt, the account choice applies', async () => {
  mockSignedIn = true;
  saveVisitChoice({ analytics: true, advertising: true });          // the visit said yes
  mockGet.mockResolvedValue({ data: { choice: { analytics: false, advertising: false, created_at: '2026-10-27T00:00:00Z' } } });
  const { container } = await render(app());
  expect(q(container, 'consent-prompt')).toBeNull();
  expect(getCurrentChoice()).toMatchObject({ analytics: false, advertising: false });
  expect(readVisitChoice()).toMatchObject({ analytics: false, advertising: false });   // replaced
  expect(mockPost).not.toHaveBeenCalled();
});

test('new account: the visit choice is saved with source signup', async () => {
  mockSignedIn = true;
  saveVisitChoice({ analytics: true, advertising: false });
  mockGet.mockResolvedValue({ data: { choice: null } });
  mockPost.mockResolvedValue({ data: { saved: true, choice: { analytics: true, advertising: false } } });
  const { container } = await render(app());
  expect(q(container, 'consent-prompt')).toBeNull();
  expect(mockPost.mock.calls[0][1]).toMatchObject({ analytics: true, advertising: false, source: 'signup' });
});

test('an existing account with no choice anywhere is asked once', async () => {
  mockSignedIn = true;
  mockGet.mockResolvedValue({ data: { choice: null } });
  const { container } = await render(app());
  expect(q(container, 'consent-prompt')).not.toBeNull();
});

test('GPC with an account that allowed advertising records a gpc opt-out', async () => {
  mockSignedIn = true;
  setGpc(true);
  mockGet.mockResolvedValue({ data: { choice: { analytics: true, advertising: true } } });
  mockPost.mockResolvedValue({ data: { saved: true, choice: { analytics: true, advertising: false } } });
  await render(app());
  expect(mockPost.mock.calls[0][1]).toMatchObject({ advertising: false, gpc: true, source: 'gpc' });
  expect(getCurrentChoice()).toMatchObject({ analytics: true, advertising: false });
});

test('backend down while signed in: falls back to the visit choice', async () => {
  mockSignedIn = true;
  saveVisitChoice({ analytics: true, advertising: false });
  mockGet.mockRejectedValue(new Error('down'));
  await render(app());
  expect(getCurrentChoice()).toMatchObject({ analytics: true, advertising: false });
});
