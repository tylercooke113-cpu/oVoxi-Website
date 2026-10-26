// Brief 26 Part B: PostHog never loads before consent; replay is off on private pages.
import { _reset, isLoaded, isPrivatePath, setPath, start, stop } from './analytics';

const posthogScripts = () => [...document.querySelectorAll('script')].filter((s) => s.src.includes('posthog'));

beforeEach(() => {
  _reset();
  document.head.innerHTML = '';
  localStorage.clear();
});

test('nothing loads until start()', () => {
  expect(isLoaded()).toBe(false);
  expect(window.posthog).toBeUndefined();
  expect(posthogScripts()).toHaveLength(0);
});

test('start() loads PostHog once with the consent-safe config', () => {
  setPath('/catalog');
  start();
  start();
  expect(isLoaded()).toBe(true);
  expect(posthogScripts()).toHaveLength(1);
  expect(posthogScripts()[0].src).toBe('https://us-assets.i.posthog.com/static/array.js');
  const [key, config] = window.posthog._i[0];
  expect(key).toMatch(/^phc_/);
  expect(config.session_recording).toEqual({
    maskAllInputs: true, maskTextSelector: '[data-private]', recordCrossOriginIframes: false });
  expect(config.disable_session_recording).toBe(false);
});

test('replay starts disabled when the first page is private', () => {
  setPath('/vault');
  start();
  expect(window.posthog._i[0][1].disable_session_recording).toBe(true);
});

test('replay stops on private pages and resumes on public ones', () => {
  setPath('/');
  start();
  window.posthog.stopSessionRecording = jest.fn();
  window.posthog.startSessionRecording = jest.fn();
  setPath('/cosign/abc');
  expect(window.posthog.stopSessionRecording).toHaveBeenCalled();
  setPath('/catalog');
  expect(window.posthog.startSessionRecording).toHaveBeenCalled();
});

test('stop() opts out and clears PostHog storage', () => {
  start();
  window.posthog.opt_out_capturing = jest.fn();
  window.posthog.stopSessionRecording = jest.fn();
  localStorage.setItem('ph_phc_x_posthog', '{}');
  stop();
  expect(window.posthog.opt_out_capturing).toHaveBeenCalled();
  expect(localStorage.getItem('ph_phc_x_posthog')).toBeNull();
});

test('stop() before any start never loads PostHog', () => {
  stop();
  expect(isLoaded()).toBe(false);
  expect(posthogScripts()).toHaveLength(0);
});

test.each([
  ['/vault', true], ['/account', true], ['/upload', true], ['/admin', true], ['/cosign/t1', true],
  ['/license/tok', true], ['/catalog/success', true], ['/appeal/x', true], ['/signup/verify', true],
  ['/login', true], ['/apply', true], ['/contact', true],
  ['/', false], ['/catalog', false], ['/catalog/track/1', false], ['/pricing', false],
  ['/license-terms', false], ['/privacy', false], ['/verify/L-1', false],
])('isPrivatePath(%s) is %s', (path, priv) => {
  expect(isPrivatePath(path)).toBe(priv);
});
