import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth, SignOutButton } from '@clerk/clerk-react';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { errorMessage } from '../sync/api';
import AgreementDoc from '../agreement/AgreementDoc';
import { authorizeApi, USE_SHORT } from '../uploaders/api';

// Brief 28 Part D2: /authorize/:token. The invited uploader reads the Upload Authorization
// (already signed by the artist), then signs with their typed name or declines. Every call
// needs them signed in with the invited email; the backend checks it (403 otherwise).

const collapse = (s) => (s || '').trim().replace(/\s+/g, ' ');
const labelCls = 'mb-1.5 block text-[13.5px] font-medium text-slate-300';
const inputCls = 'w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white focus:border-electric/70 focus:outline-none';
const primaryCls = 'inline-flex items-center gap-2 rounded-full bg-gradient-brand px-6 py-2.5 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(180,79,212,0.6)] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none';
const ghostCls = 'rounded-full border border-white/10 px-5 py-2.5 text-sm text-slate-300 transition-colors hover:border-electric/50 hover:text-white disabled:opacity-40';

const HANDLED = {
  active: ['Already signed', 'This authorization is already signed. You can upload for this artist from the Upload page.'],
  declined: ['Already declined', 'This invitation was declined. If that was a mistake, ask the artist to send a new one.'],
  revoked: ['Invitation cancelled', 'The artist cancelled this invitation. Ask them to send a new one if you still need access.'],
  expired: ['Link expired', 'This link has expired. Ask the artist to send a new invitation from their Vault.'],
};

const Centered = ({ icon: Icon, color, title, children, testid }) => (
  <div className="flex min-h-screen items-center justify-center bg-ink px-6 pt-20" data-testid={testid}>
    <div className="max-w-md rounded-2xl border border-white/10 bg-white/[0.02] p-10 text-center">
      {Icon && <Icon size={44} className={`mx-auto ${color}`} />}
      <h2 className="mt-5 font-heading text-2xl font-semibold text-white">{title}</h2>
      {children && <div className="mt-3 text-sm leading-relaxed text-slate-400">{children}</div>}
    </div>
  </div>
);

export default function AuthorizePage() {
  const { token } = useParams();
  const { isLoaded, isSignedIn, getToken: clerkGetToken } = useAuth();
  // Hold getToken in a ref so a new function identity never re-runs the load effect.
  const tokenRef = useRef(clerkGetToken);
  tokenRef.current = clerkGetToken;
  const getToken = useCallback((...a) => tokenRef.current(...a), []);
  const [phase, setPhase] = useState('loading');   // loading | ready | wrong | invalid | handled | signed | declined
  const [msg, setMsg] = useState('');
  const [handled, setHandled] = useState('');
  const [data, setData] = useState(null);
  const [adult, setAdult] = useState(false);
  const [agree, setAgree] = useState(false);
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [declineOpen, setDeclineOpen] = useState(false);
  const [reason, setReason] = useState('');

  const fail = useCallback((ex) => {
    const status = ex?.response?.status;
    const detail = ex?.response?.data?.detail;
    if (status === 409 && detail && typeof detail === 'object') {
      setHandled(detail.status); setPhase('handled'); return true;
    }
    if (status === 403) { setMsg(errorMessage(ex)); setPhase('wrong'); return true; }
    if (status === 404) { setMsg(errorMessage(ex)); setPhase('invalid'); return true; }
    return false;
  }, []);

  const load = useCallback(async () => {
    setPhase('loading');
    try {
      setData(await authorizeApi.get(getToken, token));
      setPhase('ready');
    } catch (ex) {
      if (!fail(ex)) { setMsg(errorMessage(ex, 'Could not load this invitation.')); setPhase('invalid'); }
    }
  }, [getToken, token, fail]);

  useEffect(() => { if (isLoaded && isSignedIn) load(); }, [isLoaded, isSignedIn, load]);

  const expected = collapse(data?.uploader_name);
  const nameMatches = !!collapse(typed) && collapse(typed).toLowerCase() === expected.toLowerCase();
  const canSign = adult && agree && nameMatches && !busy;

  const sign = async () => {
    setBusy(true); setErr('');
    try {
      await authorizeApi.sign(getToken, token, {
        typed_signature: collapse(typed), adult_confirmed: adult, text_sha256: data.text_sha256 });
      setPhase('signed');
    } catch (ex) {
      if (!fail(ex)) setErr(errorMessage(ex, 'Could not sign. Please try again.'));
    } finally { setBusy(false); }
  };

  const decline = async () => {
    setBusy(true); setErr('');
    try {
      await authorizeApi.decline(getToken, token, collapse(reason));
      setPhase('declined');
    } catch (ex) {
      if (!fail(ex)) setErr(errorMessage(ex, 'Could not record your answer. Please try again.'));
    } finally { setBusy(false); }
  };

  if (!isLoaded) return null;

  if (!isSignedIn) {
    const next = encodeURIComponent(`/authorize/${token}`);
    return (
      <Centered title="Sign in to review this invitation" testid="authorize-signed-out">
        <p>An artist invited you to upload songs for them on OVOXI. Sign in with the email address the invitation was sent to.</p>
        <p className="mt-2">New to OVOXI? Create a free account with that email.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link to={`/login?next=${next}`} className={primaryCls}>Sign in</Link>
          <Link to={`/signup?as=uploader&next=${next}`} className={ghostCls}>Create account</Link>
        </div>
      </Centered>
    );
  }

  if (phase === 'loading') {
    return <div className="flex min-h-screen items-center justify-center bg-ink"><Loader2 size={28} className="animate-spin text-electric" /></div>;
  }
  if (phase === 'wrong') {
    return (
      <Centered icon={AlertCircle} color="text-amber-400" title="Wrong account" testid="authorize-wrong">
        <p>{msg}</p>
        <p className="mt-2">You're signed in with a different email. Sign out, then sign in with the invited email.</p>
        <div className="mt-6 flex justify-center">
          <SignOutButton redirectUrl={`/login?next=${encodeURIComponent(`/authorize/${token}`)}`}>
            <button type="button" className={primaryCls}>Sign out and switch</button>
          </SignOutButton>
        </div>
      </Centered>
    );
  }
  if (phase === 'invalid') {
    return <Centered icon={AlertCircle} color="text-red-400" title="Link not valid" testid="authorize-invalid">{msg}</Centered>;
  }
  if (phase === 'handled') {
    const [title, body] = HANDLED[handled] || ['Already handled', 'This invitation was already answered.'];
    return <Centered icon={AlertCircle} color="text-amber-400" title={title} testid="authorize-handled">{body}</Centered>;
  }
  if (phase === 'signed') {
    return (
      <Centered icon={CheckCircle2} color="text-cyan" title={`You can now upload for ${data?.artist_name || 'this artist'}`} testid="authorize-signed">
        <p>We emailed a signed copy to you, the artist and OVOXI. On the Upload page, pick the artist under "Uploading for".</p>
        <div className="mt-6 flex justify-center"><Link to="/upload" className={primaryCls}>Go to Upload</Link></div>
      </Centered>
    );
  }
  if (phase === 'declined') {
    return <Centered icon={AlertCircle} color="text-amber-400" title="You declined" testid="authorize-declined">
      We let the artist know. Nothing was signed.</Centered>;
  }

  return (
    <div className="min-h-screen bg-ink px-6 pb-16 pt-28" data-testid="authorize-ready">
      <div className="mx-auto max-w-2xl">
        <p className="text-xs uppercase tracking-[0.18em] text-electric">Upload Authorization</p>
        <h1 className="mt-1 font-heading text-3xl font-semibold text-white">{data.artist_name} wants you to upload songs for them</h1>
        <p className="mb-5 mt-2 text-sm text-slate-400">
          Invited: <b className="font-medium text-white">{data.uploader_email}</b>, as {data.uploader_role}. Uses you can set:{' '}
          {(data.uses || []).map((u) => USE_SHORT[u] || u).join(' and ')}.
        </p>
        <ul className="mb-5 list-disc space-y-1.5 rounded-2xl border border-white/10 bg-white/[0.02] p-6 pl-10 text-sm text-slate-300 marker:text-slate-600">
          <li>{data.artist_name} has already signed. Your signature completes it, and you can upload for them right after.</li>
          <li>You can upload songs and set only the uses above. You can't take songs down, turn on Exclusive or see their Wallet.</li>
        </ul>
        <div tabIndex={0} aria-label="Upload Authorization text"
          className="h-[340px] overflow-auto rounded-xl border border-white/10 bg-white px-6 py-[22px] font-serif text-[13.5px] leading-[1.55] text-[#111]">
          <AgreementDoc blocks={data.blocks || []} />
        </div>
        <p className="mt-1.5 text-[11.5px] text-slate-500">The summary above is for convenience only. The Authorization is what you are signing.</p>

        {!declineOpen ? (
          <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <label className="mb-2.5 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
              <input type="checkbox" data-testid="adult" className="mt-1 accent-[#9B59D4]" checked={adult} onChange={(e) => setAdult(e.target.checked)} />
              <span>I am 18 or older. If I'm accepting for a company, I'm allowed to accept for it.</span>
            </label>
            <label className="mb-4 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
              <input type="checkbox" data-testid="agree" className="mt-1 accent-[#9B59D4]" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
              <span>I have read and agree to the Upload Authorization. I agree to sign electronically, and that my typed name is my legal signature.</span>
            </label>
            <label className={labelCls} htmlFor="auth-sig">Type your name to sign</label>
            <input id="auth-sig" type="text" autoComplete="off" className={inputCls} placeholder={expected}
              value={typed} onChange={(e) => setTyped(e.target.value)} />
            <div className={`my-1.5 flex min-h-[52px] items-end border-b border-white/10 px-0.5 py-1.5 font-serif text-[28px] italic ${collapse(typed) ? 'text-white' : 'text-[#333]'}`}>
              {collapse(typed) || 'Your signature'}
            </div>
            <p className="text-xs text-slate-500">
              Must match the name {data.artist_name} entered: <b className="font-medium text-slate-300">{expected}</b>. If that's wrong, ask them to cancel this invitation and send a new one.
            </p>
            <div className="mt-2 min-h-[18px] text-[13px] text-red-400" role="alert">
              {err || (collapse(typed) && !nameMatches ? 'The name must match exactly.' : '')}
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
              <button type="button" onClick={() => { setErr(''); setDeclineOpen(true); }} className="text-sm text-slate-400 hover:text-white">Decline</button>
              <button type="button" onClick={sign} disabled={!canSign} className={primaryCls}>
                {busy && <Loader2 size={16} className="animate-spin" />}Sign
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <label className={labelCls} htmlFor="auth-decline">Decline this invitation (reason optional)</label>
            <input id="auth-decline" type="text" maxLength={500} className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} />
            <p className="mt-1 text-xs text-slate-500">We'll tell {data.artist_name} you declined. Nothing is signed.</p>
            <div className="mt-2 min-h-[18px] text-[13px] text-red-400" role="alert">{err}</div>
            <div className="mt-2 flex flex-wrap justify-end gap-2">
              <button type="button" className={ghostCls} onClick={() => setDeclineOpen(false)} disabled={busy}>Back</button>
              <button type="button" onClick={decline} disabled={busy} data-testid="confirm-decline"
                className="inline-flex items-center gap-2 rounded-full border border-red-400/40 px-6 py-2.5 text-sm text-red-300 hover:bg-red-400/10 disabled:opacity-60">
                {busy && <Loader2 size={16} className="animate-spin" />}Decline
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
