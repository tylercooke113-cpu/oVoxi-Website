import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { toast } from 'sonner';
import { errorMessage } from '../sync/api';
import { gpcOn, postChoice, saveVisitChoice, setCurrentChoice } from '../lib/consent';
import useConsent from './useConsent';
import { GPC_NOTE, ToggleRow } from './ConsentPrompt';

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : '');

// The two choices, used on /privacy-choices and in My account. Signed out, a save applies
// to this visit and is recorded; signed in, it is saved to the account (Data Collection
// Policy sections 4 and 5).
export default function PrivacyChoicesPanel({ source = 'privacy_choices' }) {
  const choice = useConsent();
  const { isSignedIn, getToken } = useAuth();
  const gpc = gpcOn();
  const [analytics, setAnalytics] = useState(false);
  const [advertising, setAdvertising] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAnalytics(!!choice?.analytics);
    setAdvertising(!!choice?.advertising);
  }, [choice]);

  const save = async () => {
    setBusy(true);
    const picked = { analytics, advertising, source };
    try {
      if (isSignedIn) {
        const res = await postChoice(picked, { getToken, isSignedIn });
        setCurrentChoice(saveVisitChoice({ ...picked, decided_at: res.choice?.created_at }));
      } else {
        const saved = saveVisitChoice(picked);
        setCurrentChoice(saved);
        postChoice(saved).catch(() => {});
      }
      toast.success(isSignedIn ? 'Your privacy choices are saved to your account.' : 'Your privacy choices are saved for this visit.');
    } catch (e) {
      toast.error(errorMessage(e, 'Could not save your choices. Please try again.'));
    } finally {
      setBusy(false);
    }
  };

  if (choice === undefined) return <p className="text-sm text-slate-400">Loading your choices…</p>;

  return (
    <div data-testid="privacy-choices-panel">
      <div className="divide-y divide-white/10 rounded-2xl border border-white/10 bg-white/[0.02] px-5">
        <ToggleRow id="choices-advertising" label="Allow OVOXI to sell or share my personal information"
          checked={gpc ? false : advertising} onChange={setAdvertising} disabled={gpc}
          note={gpc ? GPC_NOTE : undefined} />
        <ToggleRow id="choices-analytics" label="Analytics and session replay"
          checked={analytics} onChange={setAnalytics} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <button type="button" onClick={save} disabled={busy} data-testid="choices-save"
          className="rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
          {busy ? 'Saving…' : 'Save choices'}
        </button>
        {choice?.decided_at && (
          <span className="text-xs text-slate-500" data-testid="choices-last-changed">Last changed {fmt(choice.decided_at)}</span>
        )}
      </div>
      <p className="mt-3 text-xs text-slate-500">
        {isSignedIn
          ? 'These choices apply whenever you are signed in, on any device.'
          : 'Signed out, these choices apply for this visit. Create an account to keep them.'}
      </p>
    </div>
  );
}
