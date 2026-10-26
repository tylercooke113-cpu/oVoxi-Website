// Visitor privacy choices (Brief 26). Categories: essential (always on, not stored),
// analytics (PostHog analytics and session replay) and advertising (selling or sharing
// personal information). Decisions (Tyler, Oct 22):
//   1. Signed out, a choice lasts for the visit (sessionStorage). A Reject from a browser
//      in a European time zone is remembered for 6 months (localStorage).
//   2. Signed in, the account's saved choice applies (GET /privacy/me).
//   3. A Global Privacy Control signal always turns advertising off.
// Every storage call is wrapped: private windows and blocked storage must never break a page.
import axios from 'axios';
import { API, maybeAuthed } from '../sync/api';

// The policies' "Last updated" date. Change all three together on a policy update.
export const POLICY_DATE = '2026-10-27';
export const POLICY_DATE_LABEL = 'October 27, 2026';

const VISIT_KEY = 'ovx_consent';
const VISITOR_KEY = 'ovx_visitor';
const EU_REJECT_KEY = 'ovx_eu_reject';
export const EU_REJECT_MS = 183 * 24 * 60 * 60 * 1000;   // 6 months

const EU_ATLANTIC = ['Atlantic/Reykjavik', 'Atlantic/Canary', 'Atlantic/Madeira', 'Atlantic/Faroe'];

export const REJECT_ALL = { analytics: false, advertising: false };
export const ACCEPT_ALL = { analytics: true, advertising: true };

const read = (store, key) => {
  try { return JSON.parse(window[store].getItem(key)); } catch { return null; }
};
const write = (store, key, value) => {
  try { window[store].setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
};
const remove = (store, key) => {
  try { window[store].removeItem(key); } catch { /* ignore */ }
};

export function gpcOn() {
  try { return navigator.globalPrivacyControl === true; } catch { return false; }
}

export function isEuTimeZone(tz) {
  let zone = tz;
  if (zone === undefined) {
    try { zone = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch { zone = ''; }
  }
  return typeof zone === 'string' && (zone.startsWith('Europe/') || EU_ATLANTIC.includes(zone));
}

// GPC wins over anything clicked or saved.
export const applyGpc = (choice) => (gpcOn() ? { ...choice, advertising: false, gpc: true } : { ...choice, gpc: false });

// A random id for this visit, so signed-out rows from one visit can be grouped.
export function visitorId() {
  const existing = read('sessionStorage', VISITOR_KEY);
  if (typeof existing === 'string') return existing;
  let id;
  try { id = crypto.randomUUID(); } catch { id = `v-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`; }
  write('sessionStorage', VISITOR_KEY, id);
  return id;
}

// This visit's choice, or a remembered European Reject, or null (ask).
export function readVisitChoice(now = Date.now()) {
  const visit = read('sessionStorage', VISIT_KEY);
  if (visit && typeof visit.analytics === 'boolean' && typeof visit.advertising === 'boolean') {
    return applyGpc(visit);
  }
  const eu = read('localStorage', EU_REJECT_KEY);
  if (eu && isEuTimeZone() && now - Date.parse(eu.decided_at) < EU_REJECT_MS) {
    return applyGpc({ ...REJECT_ALL, decided_at: eu.decided_at, policy_date: eu.policy_date, source: 'prompt' });
  }
  return null;
}

export function saveVisitChoice({ analytics, advertising, source = 'prompt', decided_at }) {
  const choice = applyGpc({
    analytics: !!analytics, advertising: !!advertising,
    decided_at: decided_at || new Date().toISOString(), policy_date: POLICY_DATE, source,
  });
  write('sessionStorage', VISIT_KEY, choice);
  if (isEuTimeZone() && !choice.analytics && !choice.advertising) {
    write('localStorage', EU_REJECT_KEY, { decided_at: choice.decided_at, policy_date: POLICY_DATE });
  } else {
    remove('localStorage', EU_REJECT_KEY);
  }
  return choice;
}

// Records the choice. Signed in, the backend saves it to the account.
export async function postChoice(choice, { getToken, isSignedIn } = {}) {
  const body = {
    analytics: !!choice.analytics, advertising: !!choice.advertising, gpc: gpcOn(),
    source: choice.source || 'prompt', policy_date: POLICY_DATE, visitor_id: visitorId(),
  };
  const opts = getToken ? await maybeAuthed(getToken, isSignedIn) : {};
  return (await axios.post(`${API}/privacy/choices`, body, opts)).data;
}

export async function fetchAccountChoice(getToken) {
  const opts = await maybeAuthed(getToken, true);
  return (await axios.get(`${API}/privacy/me`, opts)).data.choice;
}

// The choice in force right now, shared by the prompt, the analytics loader and the
// choices pages. undefined = not known yet, null = nobody has chosen (show the prompt).
let current;
const listeners = new Set();
export const getCurrentChoice = () => current;
export function setCurrentChoice(choice) {
  current = choice === null || choice === undefined ? choice : applyGpc(choice);
  listeners.forEach((fn) => fn(current));
}
export function subscribeChoice(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// Leftover PostHog storage from before consent existed, or after a Reject.
export function clearAnalyticsStorage() {
  try {
    Object.keys(localStorage).filter((k) => k.startsWith('ph_')).forEach((k) => localStorage.removeItem(k));
  } catch { /* ignore */ }
  try {
    const host = window.location.hostname;
    const domains = ['', host, `.${host.replace(/^www\./, '')}`];
    document.cookie.split(';').map((c) => c.split('=')[0].trim()).filter((n) => n.startsWith('ph_'))
      .forEach((name) => domains.forEach((d) => {
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${d ? `; domain=${d}` : ''}`;
      }));
  } catch { /* ignore */ }
}

// The prerender (react-snap) must not capture the prompt in the static HTML.
export const isPrerender = () => {
  try { return navigator.userAgent === 'ReactSnap'; } catch { return false; }
};
