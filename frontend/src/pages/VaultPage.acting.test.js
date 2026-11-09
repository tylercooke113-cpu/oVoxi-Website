/**
 * Brief 28 D4: the Vault in acting mode. Children are stubbed; the page logic runs for real.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

let mockUser = { firstName: 'Sam', lastName: 'Ortiz', publicMetadata: { role: 'artist' }, unsafeMetadata: {} };
let mockParams = new URLSearchParams();
const mockSetParams = jest.fn();
const mockArtists = jest.fn();
const mockGet = jest.fn();
const mockStatus = jest.fn();
const mockGetToken = async () => 't';
jest.mock('@clerk/clerk-react', () => ({
  useUser: () => ({ isLoaded: true, isSignedIn: true, user: mockUser }),
  useAuth: () => ({ getToken: mockGetToken }),
  SignOutButton: ({ children }) => children,
}));
jest.mock('react-router-dom', () => ({
  Navigate: ({ to }) => <div data-testid="navigate">{to}</div>,
  Link: ({ to, children }) => <a href={to}>{children}</a>,
  useNavigate: () => jest.fn(),
  useSearchParams: () => [mockParams, mockSetParams],
}), { virtual: true });
jest.mock('axios', () => ({ get: (...a) => mockGet(...a) }));
jest.mock('../uploaders/api', () => ({ uploaderApi: { artists: (...a) => mockArtists(...a) } }));
jest.mock('../agreement/useAgreementStatus', () => ({
  useAgreementStatus: (...a) => { mockStatus(...a); return {
    status: { signed: true, agreement: { signed_at: '2026-10-01' }, legal_name: 'Sam Ortiz' }, refresh: jest.fn(), needsSignature: false }; },
}));
jest.mock('../agreement/agreementApi', () => ({ openAgreementPdf: jest.fn(), formatSignedDate: () => 'Oct 1, 2026' }));
jest.mock('../agreement/AgreementModal', () => () => null);
jest.mock('../sync/TrackSyncPanel', () => ({ getToken, acting }) => (
  <div data-testid="panel">{acting ? `acting:${acting.artist_name}:${getToken.actingFor}` : 'own'}</div>));
jest.mock('../sync/SyncProfileTab', () => () => <div>profile</div>);
jest.mock('../sync/NotIntendedRemove', () => () => <div data-testid="ni" />);
jest.mock('../wallet/WalletTab', () => () => <div>wallet</div>);
jest.mock('../uploaders/AuthorizedUploadersTab', () => () => <div>uploaders</div>);
jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

import VaultPage from './VaultPage';

global.IS_REACT_ACT_ENVIRONMENT = true;
const JANE = { artist_user_id: 'a_jane', artist_name: 'Jane Rivers', licensor_name: 'Jane Q Smith', uses: ['sync'], is_ovoxi: false };
const TRACK = { id: 't1', track_name: 'Midnight Ferry', genre: 'R&B', upload_date: '2026-10-29', status: 'completed', consent: { sync: true },
  uploaded_by: { name: 'Sam Ortiz' } };

let c;
async function render() {
  c = document.createElement('div'); document.body.appendChild(c);
  await act(async () => { createRoot(c).render(<VaultPage />); });
}
const q = (s) => c.querySelector(s);
const tabs = () => [...c.querySelectorAll('[role="tab"]')].map((t) => t.textContent);

beforeEach(() => {
  document.body.innerHTML = '';
  mockUser = { firstName: 'Sam', lastName: 'Ortiz', publicMetadata: { role: 'artist' }, unsafeMetadata: {} };
  mockParams = new URLSearchParams();
  [mockArtists, mockGet, mockStatus, mockSetParams].forEach((m) => m.mockReset());
  mockArtists.mockResolvedValue([JANE]);
  mockGet.mockResolvedValue({ data: [TRACK] });
});

test('own Vault: no banner, all tabs, no X-Acting-For', async () => {
  await render();
  expect(q('[data-testid="vault-acting-banner"]')).toBeNull();
  expect(tabs()).toEqual(['My Tracks', 'Sync Profile', 'Wallet', 'Authorized uploaders']);
  expect(mockGet.mock.calls[0][1].headers['X-Acting-For']).toBeUndefined();
  expect(q('[data-testid="vault-for-picker"]')).not.toBeNull();       // Sam also uploads for Jane
  expect(q('[data-testid="vault-uploaded-by-t1"]').textContent).toBe('Uploaded by Sam Ortiz');
  expect(q('[data-testid="ni"]')).not.toBeNull();                      // D5: the artist can remove
});

test('?for=artist: banner, artist catalog via X-Acting-For, only Tracks, nothing private', async () => {
  mockParams = new URLSearchParams('for=a_jane');
  await render();
  expect(q('[data-testid="vault-acting-banner"]').textContent).toContain('Acting for Jane Rivers');
  expect(c.textContent).toContain("Jane Rivers's Vault");
  expect(tabs()).toEqual(['Tracks']);
  expect(c.textContent).not.toContain('Artist Agreement signed');
  expect(mockGet.mock.calls.at(-1)[1].headers['X-Acting-For']).toBe('a_jane');
  expect(q('[data-testid="panel"]').textContent).toBe('acting:Jane Rivers:a_jane');
  expect(q('[data-testid="ni"]')).toBeNull();                          // D5: never for uploaders
  expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
});

test('?for= an artist you are not authorized for: refused, nothing fetched', async () => {
  mockParams = new URLSearchParams('for=a_other');
  await render();
  expect(q('[data-testid="vault-acting-unknown"]')).not.toBeNull();
  expect(mockGet).not.toHaveBeenCalled();
});

test('uploader-only: opens on its first artist, no "Back to my Vault", no agreement status', async () => {
  mockUser = { firstName: 'Sam', lastName: 'Ortiz', publicMetadata: {}, unsafeMetadata: { account_type: 'uploader' } };
  await render();
  expect(q('[data-testid="vault-acting-banner"]').textContent).not.toContain('Back to my Vault');
  expect(mockGet.mock.calls.at(-1)[1].headers['X-Acting-For']).toBe('a_jane');
  expect(mockStatus.mock.calls.every((call) => call[1] === false)).toBe(true);
});

test('uploader-only with no artists: explanation, nothing fetched', async () => {
  mockUser = { publicMetadata: {}, unsafeMetadata: { account_type: 'uploader' } };
  mockArtists.mockResolvedValue([]);
  await render();
  expect(q('[data-testid="vault-no-artists"]')).not.toBeNull();
  expect(mockGet).not.toHaveBeenCalled();
});
