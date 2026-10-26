// Brief 26 decisions 1 and 3: visit choices, the European Reject, GPC.
jest.mock('axios', () => ({ post: jest.fn(), get: jest.fn() }));
jest.mock('../sync/api', () => ({
  API: 'https://api.test/api',
  maybeAuthed: async (getToken, isSignedIn) => (isSignedIn ? { headers: { Authorization: `Bearer ${await getToken()}` } } : {}),
}));

import axios from 'axios';
import {
  EU_REJECT_MS, POLICY_DATE, applyGpc, clearAnalyticsStorage, getCurrentChoice, isEuTimeZone,
  postChoice, readVisitChoice, saveVisitChoice, setCurrentChoice, subscribeChoice, visitorId,
} from './consent';

const setGpc = (on) => Object.defineProperty(navigator, 'globalPrivacyControl', { value: on, configurable: true });
const setZone = (zone) => jest.spyOn(Intl, 'DateTimeFormat').mockReturnValue({ resolvedOptions: () => ({ timeZone: zone }) });

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  setGpc(undefined);
  jest.restoreAllMocks();
  axios.post.mockReset();
});

test('no choice means ask', () => {
  expect(readVisitChoice()).toBeNull();
});

test('a choice lasts for the visit', () => {
  setZone('America/New_York');
  saveVisitChoice({ analytics: true, advertising: false });
  expect(readVisitChoice()).toMatchObject({ analytics: true, advertising: false, policy_date: POLICY_DATE });
  sessionStorage.clear();                         // a new visit
  expect(readVisitChoice()).toBeNull();
});

test('a US Reject is not remembered past the visit', () => {
  setZone('America/Chicago');
  saveVisitChoice({ analytics: false, advertising: false });
  sessionStorage.clear();
  expect(readVisitChoice()).toBeNull();
});

test('a European Reject is remembered for 6 months', () => {
  setZone('Europe/Paris');
  saveVisitChoice({ analytics: false, advertising: false });
  sessionStorage.clear();
  expect(readVisitChoice()).toMatchObject({ analytics: false, advertising: false });
  expect(readVisitChoice(Date.now() + EU_REJECT_MS + 1000)).toBeNull();
});

test('a later European Accept forgets the remembered Reject', () => {
  setZone('Europe/Berlin');
  saveVisitChoice({ analytics: false, advertising: false });
  saveVisitChoice({ analytics: true, advertising: true });
  sessionStorage.clear();
  expect(readVisitChoice()).toBeNull();
});

test.each([
  ['Europe/London', true], ['Atlantic/Reykjavik', true], ['Atlantic/Canary', true],
  ['America/New_York', false], ['Atlantic/Bermuda', false], ['', false],
])('isEuTimeZone(%s) is %s', (zone, eu) => {
  expect(isEuTimeZone(zone)).toBe(eu);
});

test('GPC forces advertising off, saved or read', () => {
  setGpc(true);
  expect(saveVisitChoice({ analytics: true, advertising: true })).toMatchObject({ advertising: false, gpc: true });
  expect(applyGpc({ analytics: true, advertising: true }).advertising).toBe(false);
  expect(readVisitChoice()).toMatchObject({ analytics: true, advertising: false });
});

test('storage that throws never breaks the page', () => {
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  expect(readVisitChoice()).toBeNull();
  expect(() => saveVisitChoice({ analytics: true, advertising: true })).not.toThrow();
  expect(typeof visitorId()).toBe('string');
});

test('postChoice sends the record, with the token when signed in', async () => {
  setGpc(true);
  axios.post.mockResolvedValue({ data: { saved: true } });
  await postChoice({ analytics: true, advertising: true, source: 'prompt' }, { getToken: async () => 'tok', isSignedIn: true });
  const [url, body, opts] = axios.post.mock.calls[0];
  expect(url).toBe('https://api.test/api/privacy/choices');
  expect(body).toMatchObject({ analytics: true, gpc: true, source: 'prompt', policy_date: POLICY_DATE });
  expect(body.visitor_id).toBe(visitorId());
  expect(opts.headers.Authorization).toBe('Bearer tok');
});

test('the shared store notifies subscribers and applies GPC', () => {
  setGpc(true);
  const seen = [];
  const off = subscribeChoice((c) => seen.push(c));
  setCurrentChoice({ analytics: true, advertising: true });
  setCurrentChoice(null);
  off();
  expect(seen[0]).toMatchObject({ analytics: true, advertising: false });
  expect(seen[1]).toBeNull();
  expect(getCurrentChoice()).toBeNull();
});

test('leftover PostHog storage is deleted', () => {
  localStorage.setItem('ph_phc_abc_posthog', '{}');
  localStorage.setItem('keep_me', '1');
  document.cookie = 'ph_phc_abc_posthog=1; path=/';
  clearAnalyticsStorage();
  expect(localStorage.getItem('ph_phc_abc_posthog')).toBeNull();
  expect(localStorage.getItem('keep_me')).toBe('1');
  expect(document.cookie).not.toContain('ph_phc_abc_posthog');
});
