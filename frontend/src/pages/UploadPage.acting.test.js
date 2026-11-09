/**
 * Brief 28 D3: the "Uploading for" picker on the Upload page. Heavy children are stubbed;
 * the page logic (who can upload for whom, banner, no "Me" for uploader-only) runs for real.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

let mockUser = { publicMetadata: {}, unsafeMetadata: {} };
const mockArtists = jest.fn();
const mockStatus = jest.fn();
jest.mock('@clerk/clerk-react', () => ({
  useAuth: () => ({ getToken: mockGetToken, isSignedIn: true, isLoaded: true }),
  useUser: () => ({ user: mockUser }),
}));
const mockGetToken = async () => 't';
jest.mock('react-router-dom', () => ({
  Link: ({ to, children }) => <a href={to}>{children}</a>,
  Navigate: () => null,
  useNavigate: () => jest.fn(),
}), { virtual: true });
jest.mock('../uploaders/api', () => ({ uploaderApi: { artists: (...a) => mockArtists(...a) } }));
jest.mock('../agreement/useAgreementStatus', () => ({
  useAgreementStatus: (...a) => { mockStatus(...a); return { status: null, refresh: jest.fn(), needsSignature: false }; },
}));
jest.mock('../agreement/AgreementModal', () => () => null);
jest.mock('../components/PageHero', () => ({ PageHero: ({ label, title }) => <h1 data-testid="hero">{label}|{title}</h1> }));
jest.mock('../components/Reveal', () => ({ Reveal: ({ children }) => <>{children}</> }));
jest.mock('framer-motion', () => ({ motion: { div: (p) => <div {...p} /> } }));
jest.mock('sonner', () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));
jest.mock('../upload/SongForm', () => ({
  __esModule: true,
  default: ({ acting }) => <div data-testid="songform">{acting ? `acting:${acting.licensor_name}:${acting.uses.join(',')}` : 'own'}</div>,
  emptySong: () => ({ key: Math.random().toString(36), form: {}, rights: {} }),
  carryOverSong: (s) => s, songMissing: () => [], songHasData: () => false, MAX_SONGS: 15,
}));
jest.mock('../upload/SongSummaryRow', () => () => null);
jest.mock('../upload/useBatchUpload', () => ({
  useBatchUpload: (opts) => { global.__actingFor = opts.actingFor; return { running: false, run: jest.fn() }; },
  APPROVAL_PENDING_MESSAGE: '', UPLOADS_PAUSED_MESSAGE: '', ARTIST_AGREEMENT_MESSAGE: '',
  ACTING_DENIED_MESSAGE: '', DAILY_LIMIT_MESSAGE: '',
}));

import UploadPage from './UploadPage';

global.IS_REACT_ACT_ENVIRONMENT = true;
const JANE = { artist_user_id: 'a_jane', artist_name: 'Jane Rivers', licensor_name: 'Jane Q Smith', uses: ['sync'], is_ovoxi: false };
const KOFI = { artist_user_id: 'a_kofi', artist_name: 'Kofi Mensah', licensor_name: 'Kofi A Mensah', uses: ['ai_training'], is_ovoxi: false };

let c;
async function render() {
  c = document.createElement('div'); document.body.appendChild(c);
  await act(async () => { createRoot(c).render(<UploadPage />); });
}
const q = (s) => c.querySelector(s);
const click = async (el) => { await act(async () => { el.click(); }); };

beforeEach(() => {
  document.body.innerHTML = '';
  mockUser = { publicMetadata: {}, unsafeMetadata: {} };
  mockArtists.mockReset(); mockStatus.mockReset(); global.__actingFor = undefined;
});

test('artist with no authorizations: no picker, own upload, agreement status loaded', async () => {
  mockArtists.mockResolvedValue([]);
  await render();
  expect(q('[data-testid="upload-acting-picker"]')).toBeNull();
  expect(q('[data-testid="songform"]').textContent).toBe('own');
  expect(mockStatus.mock.calls.at(-1)[1]).toBe(true);
});

test('artist who also uploads for others: "Me" plus each artist; picking one acts for them', async () => {
  mockArtists.mockResolvedValue([JANE, KOFI]);
  await render();
  expect(q('[data-testid="upload-for-me"]').getAttribute('aria-checked')).toBe('true');
  await click(q('[data-testid="upload-for-a_kofi"]'));
  expect(q('[data-testid="upload-acting-banner"]').textContent).toContain('Acting for Kofi Mensah');
  expect(q('[data-testid="songform"]').textContent).toBe('acting:Kofi A Mensah:ai_training');
  expect(global.__actingFor).toBe('a_kofi');
  expect(q('[data-testid="hero"]').textContent).toContain('Uploading for Kofi Mensah');
  await click(q('[data-testid="upload-for-me"]'));
  expect(q('[data-testid="upload-acting-banner"]')).toBeNull();
  expect(global.__actingFor).toBeNull();
});

test('uploader-only login: no "Me", starts on the first artist, never loads the Artist Agreement', async () => {
  mockUser = { publicMetadata: {}, unsafeMetadata: { account_type: 'uploader' } };
  mockArtists.mockResolvedValue([JANE]);
  await render();
  expect(q('[data-testid="upload-for-me"]')).toBeNull();
  expect(q('[data-testid="upload-for-a_jane"]').getAttribute('aria-checked')).toBe('true');
  expect(global.__actingFor).toBe('a_jane');
  expect(mockStatus.mock.calls.every((call) => call[1] === false)).toBe(true);
  expect(c.textContent).not.toMatch(/[\u2013\u2014]/);
});

test('uploader-only login with no artists sees an explanation, not the form', async () => {
  mockUser = { publicMetadata: {}, unsafeMetadata: { account_type: 'uploader' } };
  mockArtists.mockResolvedValue([]);
  await render();
  expect(q('[data-testid="upload-no-artists"]')).not.toBeNull();
  expect(q('[data-testid="upload-form"]')).toBeNull();
});
