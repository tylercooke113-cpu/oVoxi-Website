import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { syncApi, errorMessage } from './api';

const USES = ['Exclusive buyout', 'National TV campaign', 'Feature film', 'Game', 'Other'];
const BUDGETS = ['Under $5,000', '$5,000 to $25,000', '$25,000 to $100,000', 'Over $100,000'];
const input = 'h-10 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-white placeholder:text-slate-600 focus:border-electric focus:outline-none';

// Self-contained so Brief 20's Pricing page can reuse it with no track.
export default function QuoteForm({ kind, track, onDone }) {
  const [f, setF] = useState({
    name: '', company: '', email: '',
    use: kind === 'buyout' ? 'Exclusive buyout' : 'National TV campaign',
    territory: '', term: '', budget: BUDGETS[1], details: '', website: '',
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState('');
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!f.name.trim() || !f.email.trim()) { setErr('Enter your name and email.'); return; }
    setBusy(true); setErr('');
    try {
      await syncApi.quote({ kind, track_id: track?.id || null, ...f });
      setDone(true);
      if (onDone) onDone();
    } catch (e2) { setBusy(false); setErr(errorMessage(e2, 'Could not send your request. Try again.')); }
  };

  if (done) {
    return (
      <p className="mt-4 rounded-xl border border-cyan/25 bg-cyan/[0.05] px-3 py-3 text-sm text-slate-200" data-testid="quote-done">
        Thanks. We'll reply to {f.email} within 2 business days.
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="mt-4" data-testid="quote-form" noValidate>
      <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">Request a licensing quote</div>
      <p className="mb-2 text-xs text-slate-500">Goes to tyler@ovoxi.net. We usually reply within 2 business days.</p>
      {/* Honeypot: real people never see or fill this. */}
      <input type="text" tabIndex={-1} autoComplete="off" value={f.website} onChange={set('website')}
        className="hidden" aria-hidden="true" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <input className={input} placeholder="Your name" value={f.name} onChange={set('name')} maxLength={120} autoComplete="name" />
        <input className={input} placeholder="Company" value={f.company} onChange={set('company')} maxLength={120} autoComplete="organization" />
      </div>
      <input type="email" className={`${input} mt-3`} placeholder="Email" value={f.email} onChange={set('email')} autoComplete="email" />
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <select className={input} value={f.use} onChange={set('use')}>{USES.map((u) => <option key={u}>{u}</option>)}</select>
        <input className={input} placeholder="Territory (e.g. Worldwide)" value={f.territory} onChange={set('territory')} maxLength={120} />
        <input className={input} placeholder="Term (e.g. 2 years)" value={f.term} onChange={set('term')} maxLength={120} />
        <select className={input} value={f.budget} onChange={set('budget')}>{BUDGETS.map((b) => <option key={b}>{b}</option>)}</select>
      </div>
      <textarea className={`${input} mt-3 h-24 py-2`} placeholder="Tell us about the project" value={f.details} onChange={set('details')} maxLength={2000} />
      {err && <p className="mt-2 text-xs text-red-300">{err}</p>}
      <button type="submit" disabled={busy} data-testid="quote-send"
        className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-full bg-gradient-brand text-sm font-medium text-white disabled:opacity-60">
        {busy ? <><Loader2 size={16} className="animate-spin" /> Sending</> : 'Send quote request'}
      </button>
    </form>
  );
}
