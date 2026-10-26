// PostHog, loaded only after the visitor accepts analytics (Brief 26 Part B).
// Before Oct 26 the snippet ran on every page with no consent; it was removed from
// public/index.html in 9522dbb. Nothing here runs until start() is called.
import { clearAnalyticsStorage } from './consent';

export const POSTHOG_KEY = 'phc_xAvL2Iq4tFmANRE7kzbKwaSqp1HJjN7x48s3vr0CMjs';
export const POSTHOG_HOST = 'https://us.i.posthog.com';

// Pages that show names, emails, splits, signatures, amounts or typed personal details.
// Session replay is off on these (Data Collection Policy section 3).
const PRIVATE_PREFIXES = [
  '/vault', '/account', '/upload', '/admin', '/cosign', '/license', '/catalog/success',
  '/appeal', '/apply', '/contact', '/signup', '/login',
];
export const isPrivatePath = (path) =>
  PRIVATE_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`));

export const POSTHOG_CONFIG = {
  api_host: POSTHOG_HOST,
  person_profiles: 'identified_only',
  capture_pageview: 'history_change',
  session_recording: {
    maskAllInputs: true,
    maskTextSelector: '[data-private]',
    recordCrossOriginIframes: false,
  },
};

let loaded = false;
let enabled = false;
let path = typeof window !== 'undefined' ? window.location.pathname : '/';

// The PostHog loader stub, as in PostHog's own snippet: it queues calls until
// array.js arrives from the assets host.
function installStub() {
  if (window.posthog && window.posthog.__SV) return;
  const ph = window.posthog || [];
  window.posthog = ph;
  ph._i = [];
  ph.init = function init(key, config, name) {
    const stubMethod = (target, method) => {
      let t = target;
      let m = method;
      const parts = method.split('.');
      if (parts.length === 2) { t = t[parts[0]]; m = parts[1]; }
      t[m] = function queued(...args) { t.push([m, ...args]); };
    };
    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.crossOrigin = 'anonymous';
    script.async = true;
    script.src = `${config.api_host.replace('.i.posthog.com', '-assets.i.posthog.com')}/static/array.js`;
    (document.head || document.body).appendChild(script);
    let u = ph;
    let label = name;
    if (label !== undefined) { u = ph[label] = []; } else { label = 'posthog'; }
    u.people = u.people || [];
    u.toString = (stub) => `posthog${label !== 'posthog' ? `.${label}` : ''}${stub ? '' : ' (stub)'}`;
    u.people.toString = () => `${u.toString(1)}.people (stub)`;
    ('init capture register register_once register_for_session unregister unregister_for_session '
      + 'getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags onFeatureFlags '
      + 'onSessionId identify setPersonProperties group resetGroups reset get_distinct_id '
      + 'get_session_id alias set_config startSessionRecording stopSessionRecording '
      + 'sessionRecordingStarted captureException opt_in_capturing opt_out_capturing '
      + 'has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug')
      .split(' ').forEach((m) => stubMethod(u, m));
    ph._i.push([key, config, name]);
  };
  ph.__SV = 1;
}

const syncRecording = () => {
  if (!loaded || !enabled) return;
  try {
    if (isPrivatePath(path)) window.posthog.stopSessionRecording();
    else window.posthog.startSessionRecording();
  } catch { /* ignore */ }
};

// Analytics on: load PostHog (once), or opt back in if it was loaded and then refused.
export function start() {
  enabled = true;
  try {
    if (!loaded) {
      installStub();
      window.posthog.init(POSTHOG_KEY, {
        ...POSTHOG_CONFIG,
        // Replay starts only on a page that allows it.
        disable_session_recording: isPrivatePath(path),
      });
      loaded = true;
    } else {
      window.posthog.opt_in_capturing();
    }
  } catch { /* analytics must never break the site */ }
  syncRecording();
}

// Analytics off: stop capturing and recording, and delete PostHog's storage.
export function stop() {
  enabled = false;
  if (loaded) {
    try {
      window.posthog.stopSessionRecording();
      window.posthog.opt_out_capturing();
    } catch { /* ignore */ }
  }
  clearAnalyticsStorage();
}

// Called on every route change.
export function setPath(nextPath) {
  path = nextPath;
  syncRecording();
}

export const isLoaded = () => loaded;

// Tests only.
export function _reset() {
  loaded = false;
  enabled = false;
  path = '/';
  delete window.posthog;
}
