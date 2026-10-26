import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { Switch } from '../components/ui/switch';
import {
  ACCEPT_ALL, REJECT_ALL, gpcOn, isPrerender, postChoice, saveVisitChoice, setCurrentChoice,
} from '../lib/consent';
import useConsent from './useConsent';

export const GPC_NOTE = "Off (your browser's Global Privacy Control is on)";

const BTN = 'rounded-full px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-electric';
// Accept and Reject look the same: neither choice is made harder to pick than the other.
const CHOICE = 'border border-white/25 bg-white/[0.06] text-white hover:bg-white/15';
const SWITCH = 'data-[state=checked]:bg-electric data-[state=unchecked]:bg-white/20';

export const ToggleRow = ({ id, label, checked, onChange, disabled, note }) => (
  <div className="flex items-start justify-between gap-4 py-2">
    <div>
      <label htmlFor={id} className="text-sm text-white">{label}</label>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </div>
    <Switch id={id} checked={checked} onCheckedChange={onChange} disabled={disabled}
      className={SWITCH} data-testid={id} aria-label={label} />
  </div>
);

// The data collection prompt. Copy is verbatim from Data Collection Policy section 4.
// A bottom card, not a modal: the page stays readable, and Esc does nothing because a
// choice is required. Shown only when nobody has chosen (see ConsentManager).
export default function ConsentPrompt() {
  const choice = useConsent();
  const { isSignedIn, getToken } = useAuth();
  const [customize, setCustomize] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [advertising, setAdvertising] = useState(false);
  const cardRef = useRef(null);
  const gpc = gpcOn();
  const open = choice === null && !isPrerender();

  useEffect(() => {
    if (open) cardRef.current?.focus();
  }, [open]);

  if (!open) return null;

  const decide = (picked) => {
    const saved = saveVisitChoice({ ...picked, source: 'prompt' });
    setCurrentChoice(saved);
    // The record is best effort: the visit's choice applies even if the network fails.
    postChoice(saved, { getToken, isSignedIn }).catch(() => {});
  };

  return (
    <div role="dialog" aria-modal="false" aria-label="Privacy choices" tabIndex={-1} ref={cardRef}
      data-testid="consent-prompt"
      className="fixed inset-x-0 bottom-0 z-50 p-3 sm:bottom-4 sm:left-4 sm:right-auto sm:max-w-md sm:p-0 focus:outline-none">
      <div className="rounded-2xl border border-white/10 bg-black/95 p-5 shadow-2xl backdrop-blur">
        <p className="text-sm leading-relaxed text-slate-300">
          OVOXI uses essential technologies to run the site. With your permission, we also use analytics
          and session replay to improve it. See our{' '}
          <Link to="/data-policy" className="text-cyan hover:underline">Data Collection Policy</Link> and{' '}
          <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link>.
        </p>

        {customize && (
          <div className="mt-3 divide-y divide-white/10 border-y border-white/10" data-testid="consent-customize">
            <ToggleRow id="consent-essential" label="Essential (always on)" checked disabled onChange={() => {}} />
            <ToggleRow id="consent-analytics" label="Analytics and session replay"
              checked={analytics} onChange={setAnalytics} />
            <ToggleRow id="consent-advertising"
              label="Advertising and data sharing"
              checked={gpc ? false : advertising} onChange={setAdvertising} disabled={gpc}
              note={gpc ? GPC_NOTE : undefined} />
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {customize ? (
            <button type="button" onClick={() => decide({ analytics, advertising })}
              className={`${BTN} bg-gradient-brand text-white`} data-testid="consent-save">Save choices</button>
          ) : (
            <>
              <button type="button" onClick={() => decide(ACCEPT_ALL)}
                className={`${BTN} ${CHOICE}`} data-testid="consent-accept">Accept all</button>
              <button type="button" onClick={() => decide(REJECT_ALL)}
                className={`${BTN} ${CHOICE}`} data-testid="consent-reject">Reject</button>
              <button type="button" onClick={() => setCustomize(true)}
                className={`${BTN} text-slate-300 hover:text-white`} data-testid="consent-customize-open">Customize</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
