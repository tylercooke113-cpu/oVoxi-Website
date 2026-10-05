import React, { useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import Modal from './Modal';
import { errorMessage } from './api';
import { checkoutApi, fmtMoney } from './checkout';
import QuoteForm from './QuoteForm';

// PRD-03 7.2 / Brief 18: pick a license tier (and term / territory), add free stems,
// or request a quote for Enterprise and Exclusive buyout.

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const input = 'h-10 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-white placeholder:text-slate-600 focus:border-electric focus:outline-none';

const LIMITS = {
  creator: 'Your own channels only. No client work, sponsored content or paid ads. Perpetual for this project.',
  digital: 'Paid ads up to $25,000 total spend, running 12 months from the license date. Organic use is perpetual.',
  campaign: 'Up to $100,000 total media spend during the term, starting on the license date. Includes out-of-home, retail, events and trade shows.',
  broadcast: 'Ads: up to $250,000 spend for the term, starting on the license date, in one country. Programs and films: perpetual in that country, plus festivals worldwide.',
  enterprise: 'Tell us what you need and we will send a custom quote.',
  buyout: 'Exclusive sync rights for this track. Priced by quote. The track leaves the library during your exclusive term.',
};

const LicenseModal = ({ track, config, onClose, refreshConfig, getToken, isSignedIn }) => {
  const [cfg, setCfg] = useState(config);
  const tierMap = useMemo(() => Object.fromEntries(cfg.tiers.map((t) => [t.id, t])), [cfg]);
  const [sel, setSel] = useState('digital');
  const [term, setTerm] = useState('1y');
  const [territory, setTerritory] = useState(cfg.countries?.[0]?.code || 'US');
  const [stems, setStems] = useState(false);
  const [form, setForm] = useState({ project: '', client: '', name: '', company: '', email: '' });
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const isQuote = sel === 'enterprise' || sel === 'buyout';
  const tier = tierMap[sel];
  const hasTerms = !!tier?.terms;
  const needsTerritory = !!tier?.needs_territory;
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setErrors({}); };

  const options = [
    ...cfg.tiers.map((t) => ({ id: t.id, label: t.label, desc: t.description, price: fmtMoney(t.price_cents) })),
    { id: 'enterprise', label: 'Enterprise', desc: 'Major campaigns, films, games', price: 'Quote' },
    {
      id: 'buyout', label: 'Exclusive buyout', price: 'Quote',
      desc: track.buyout_allowed ? 'Exclusive rights to this track' : 'Not offered for this track',
      disabled: !track.buyout_allowed,
    },
  ];

  const total = useMemo(() => {
    if (isQuote) return null;
    if (hasTerms) return tier.terms.find((t) => t.id === term)?.price_cents;
    return tier.price_cents;
  }, [isQuote, hasTerms, tier, term]);

  const pick = (id, disabled) => {
    if (disabled) return;
    setSel(id);
    setErrors({});
    const t = tierMap[id];
    if (t?.terms) setTerm(t.terms[0].id);
  };

  const submit = async (e) => {
    e.preventDefault();
    const next = {};
    if (!form.project.trim()) next.project = 'Name the project this license is for.';
    if (!form.name.trim()) next.name = 'Enter your name.';
    if (!EMAIL_RE.test(form.email.trim())) next.email = 'Enter a valid email.';
    if (!agreed) next.terms = 'Agree to the license terms to continue.';
    if (Object.keys(next).length) { setErrors(next); return; }
    setSubmitting(true);
    try {
      const { checkout_url: url } = await checkoutApi.start({
        track_id: track.id, tier: sel, term: hasTerms ? term : null,
        territory: needsTerritory ? territory : null, include_stems: cfg.stems_available && stems,
        buyer_name: form.name.trim(), buyer_company: form.company.trim(), buyer_email: form.email.trim(),
        project_name: form.project.trim(), project_client: form.client.trim(),
        accept_terms: true, terms_version: cfg.terms_version,
      }, getToken, isSignedIn);
      window.location.assign(url);
    } catch (err) {
      setSubmitting(false);
      if (err?.response?.status === 409) {
        const fresh = await refreshConfig();
        if (fresh?.can_checkout) setCfg(fresh);
        setAgreed(false);
        setErrors({ form: 'The license terms have changed. Review them and agree again.' });
        return;
      }
      setErrors({ form: errorMessage(err, 'Could not start checkout. Try again.') });
    }
  };

  return (
    <Modal open title={`License "${track.track_name}"`} onClose={submitting ? () => {} : onClose}>
      <p className="-mt-2 mb-4 text-sm text-slate-400">{track.artist_display_name}</p>

      <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">Choose a license</div>
      <div className="space-y-2" data-testid="license-modal">
        {options.map((o) => (
          <label key={o.id}
            className={`flex items-center justify-between rounded-xl border px-3.5 py-2.5 ${o.disabled ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'} ${o.id === sel ? 'border-electric-light bg-electric/[0.08]' : 'border-white/10'}`}>
            <span className="flex items-center gap-3">
              <input type="radio" name="lic" disabled={o.disabled} checked={o.id === sel}
                onChange={() => pick(o.id, o.disabled)} className="accent-[#B44FD4]" />
              <span>
                <span className="block text-sm text-white">{o.label}</span>
                <span className="block text-xs text-slate-500">{o.desc}</span>
              </span>
            </span>
            <b className="text-sm font-medium text-white">{o.price}</b>
          </label>
        ))}
      </div>

      {hasTerms && (
        <div className="mt-3">
          <label htmlFor="lic-term" className="mb-1 block text-xs text-slate-300">Term</label>
          <select id="lic-term" className={input} value={term} onChange={(e) => setTerm(e.target.value)}>
            {tier.terms.map((t) => <option key={t.id} value={t.id}>{t.label} ({fmtMoney(t.price_cents)})</option>)}
          </select>
        </div>
      )}
      {needsTerritory && (
        <div className="mt-3">
          <label htmlFor="lic-terr" className="mb-1 block text-xs text-slate-300">Territory (one country)</label>
          <select id="lic-terr" className={input} value={territory} onChange={(e) => setTerritory(e.target.value)}>
            {cfg.countries.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        </div>
      )}

      <p className="mt-3 rounded-xl border border-cyan/25 bg-cyan/[0.05] px-3 py-2 text-xs text-slate-300">{LIMITS[sel]}</p>

      {!isQuote && (
        <div className="mt-3">
          <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">Files</div>
          {cfg.stems_available ? (
            <label className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
              <input type="checkbox" checked={stems} onChange={(e) => setStems(e.target.checked)} className="mt-1 accent-[#B44FD4]" />
              Include stems and instrumental (free)
            </label>
          ) : (
            <p className="text-xs text-slate-500">You'll get WAV and MP3.</p>
          )}
        </div>
      )}

      {isQuote ? (
        <QuoteForm kind={sel === 'buyout' ? 'buyout' : 'enterprise'} track={track} onDone={() => {}} />
      ) : (
        <form onSubmit={submit} noValidate className="mt-4">
          <div className="space-y-3">
            <div>
              <label htmlFor="lic-project" className="mb-1 block text-xs text-slate-300">Project name</label>
              <input id="lic-project" className={input} value={form.project} onChange={set('project')} maxLength={120} placeholder="Summer campaign teaser" />
              {errors.project && <p className="mt-1 text-xs text-red-300">{errors.project}</p>}
            </div>
            <div>
              <label htmlFor="lic-client" className="mb-1 block text-xs text-slate-300">Client (optional)</label>
              <input id="lic-client" className={input} value={form.client} onChange={set('client')} maxLength={120} placeholder="Acme Inc." />
            </div>
            <div>
              <label htmlFor="lic-name" className="mb-1 block text-xs text-slate-300">Your name</label>
              <input id="lic-name" className={input} value={form.name} onChange={set('name')} maxLength={120} placeholder="Dana Rivera" autoComplete="name" />
              {errors.name && <p className="mt-1 text-xs text-red-300">{errors.name}</p>}
            </div>
            <div>
              <label htmlFor="lic-company" className="mb-1 block text-xs text-slate-300">Company (optional)</label>
              <input id="lic-company" className={input} value={form.company} onChange={set('company')} maxLength={120} placeholder="Rivera Studio" autoComplete="organization" />
            </div>
            <div>
              <label htmlFor="lic-email" className="mb-1 block text-xs text-slate-300">Email for your license</label>
              <input id="lic-email" type="email" className={input} value={form.email} onChange={set('email')} placeholder="dana@studio.com" autoComplete="email" />
              {errors.email && <p className="mt-1 text-xs text-red-300">{errors.email}</p>}
            </div>
          </div>
          <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
            <input type="checkbox" checked={agreed} onChange={(e) => { setAgreed(e.target.checked); setErrors({}); }} className="mt-1 accent-[#B44FD4]" />
            <span>I agree to the <a href={cfg.terms_url} target="_blank" rel="noreferrer" className="text-cyan hover:underline">oVoxi Music License Terms</a>.</span>
          </label>
          {errors.terms && <p className="mt-1 text-xs text-red-300">{errors.terms}</p>}
          {errors.form && <p className="mt-3 rounded-xl border border-red-400/30 bg-red-400/[0.06] px-3 py-2 text-xs text-red-200">{errors.form}</p>}
          <div className="mt-5 flex items-center justify-between gap-2.5">
            <span className="text-sm text-slate-400">Total <b className="text-white">{fmtMoney(total)}</b> + tax</span>
            <button type="submit" disabled={submitting} data-testid="license-continue"
              className="flex h-11 items-center justify-center gap-2 rounded-full bg-gradient-brand px-6 text-sm font-medium text-white disabled:opacity-60">
              {submitting ? <><Loader2 size={16} className="animate-spin" /> Opening checkout</> : 'Continue to payment'}
            </button>
          </div>
          <p className="mt-2 text-center text-xs text-slate-500">Tax is calculated at checkout. Payment is handled by Stripe.</p>
        </form>
      )}
    </Modal>
  );
};

export default LicenseModal;
