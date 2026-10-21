/**
 * Brief 23 Part A: the Sync Profile tab renders three states without any request that
 * returns 403, and waits for the Vault's tracks before deciding. react-dom + act in
 * jsdom; no new deps.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('axios', () => ({ put: jest.fn() }));
jest.mock('lucide-react', () => ({ Loader2: () => null }));
// react-router-dom v7 is ESM-only; jest's CJS resolver can't load it, so mock virtually.
jest.mock('react-router-dom', () => ({ Link: ({ to, children }) => <a href={to}>{children}</a> }), { virtual: true });
jest.mock('../components/ui/input', () => ({ Input: (p) => <input {...p} /> }));
jest.mock('../components/ui/label', () => ({ Label: ({ children, ...p }) => <label {...p}>{children}</label> }));
jest.mock('../components/ui/textarea', () => ({ Textarea: (p) => <textarea {...p} /> }));
jest.mock('./PublicPageParts', () => ({ Avatar: () => null }));
jest.mock('./labels', () => ({ reasonText: (s) => s }));

const mockGetProfile = jest.fn();
jest.mock('./api', () => ({
  api: {
    getProfile: (...a) => mockGetProfile(...a),
    putProfile: jest.fn(), presignPhoto: jest.fn(), completePhoto: jest.fn(), deletePhoto: jest.fn(),
  },
  errorMessage: (e) => String(e),
}));

import SyncProfileTab from './SyncProfileTab';

global.IS_REACT_ACT_ENVIRONMENT = true;
const getToken = async () => 't';

async function renderTab(props) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => { root.render(<SyncProfileTab getToken={getToken} {...props} />); });
  return { container, root };
}

// The blurred backdrop must be truly inert and hidden from assistive tech.
function expectInertBackdrop(container) {
  const backdrop = container.querySelector('[inert]');
  expect(backdrop).not.toBeNull();
  expect(backdrop.hasAttribute('inert')).toBe(true);
  expect(backdrop.getAttribute('aria-hidden')).toBe('true');
}

beforeEach(() => { mockGetProfile.mockReset(); mockGetProfile.mockResolvedValue({}); });

test('pending account: no profile request, shows the inert pending card', async () => {
  const { container } = await renderTab({ role: undefined, tracks: [], tracksLoaded: true });
  expect(mockGetProfile).not.toHaveBeenCalled();
  expect(container.textContent).toContain('Your account is pending approval');
  expectInertBackdrop(container);
});

test('approved artist, no tracks: no request, inert upload card with /upload link', async () => {
  const { container } = await renderTab({ role: 'artist', tracks: [], tracksLoaded: true });
  expect(mockGetProfile).not.toHaveBeenCalled();
  expect(container.textContent).toContain('Upload your first track to customize your sync profile.');
  expect(container.querySelector('a[href="/upload"]')).not.toBeNull();
  expectInertBackdrop(container);
});

test('approved artist with tracks: fetches the profile once and shows the form', async () => {
  const { container } = await renderTab({ role: 'artist', tracks: [{ id: '1', track_name: 'Song' }], tracksLoaded: true });
  expect(mockGetProfile).toHaveBeenCalledTimes(1);
  expect(container.textContent).toContain('Display name');
  expect(container.querySelector('[inert]')).toBeNull();
});

test('tracks load after mount: waits, then lands on the form with exactly one fetch', async () => {
  const { container, root } = await renderTab({ role: 'artist', tracks: [], tracksLoaded: false });
  expect(mockGetProfile).not.toHaveBeenCalled();
  expect(container.textContent).not.toContain('Display name');
  expect(container.textContent).not.toContain('Upload your first track');
  await act(async () => {
    root.render(<SyncProfileTab getToken={getToken} role="artist"
      tracks={[{ id: '1', track_name: 'Song' }]} tracksLoaded />);
  });
  expect(mockGetProfile).toHaveBeenCalledTimes(1);
  expect(container.textContent).toContain('Display name');
});
