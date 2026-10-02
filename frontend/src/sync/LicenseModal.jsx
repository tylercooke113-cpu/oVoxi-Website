import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import Modal from './Modal';
import { errorMessage } from './api';
import { checkoutApi, fmtMoney } from './checkout';

// PRD-03 7.2 step 2: tier, stems add-on, buyer details, terms. Submitting sends the
// buyer to Stripe's hosted checkout.

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const input = 'h-10 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-white placeholder:text-slate-600 focus:border-electric focus:outline-none';

const LicenseModal = ({ track, config, onClose, refreshConfig, getToken, isSignedIn }) => {
  const [tier, setTier] = useState(config.tiers[0].id);
  const [stems, setStems] = useState(false);
  const [form, setForm] = useState({ project: '', client: '', name: '', company: '', email: '' });
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [cfg, setCfg] = useState(config);

  const selected = cfg.tiers.find((t) => t.id === tier) || cfg.tiers[0];
  const withStems = cfg.stems_available && stems;
  const total = withStems ? selected.price_with_stems_cents : selected.price_cents;
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setErrors({}); };

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
        track_id: track.id, tier, include_stems: withStems, buyer_name: form.name.trim(),
        buyer_company: form.company.trim(), buyer_email: form.email.trim(),
        project_name: form.project.trim(), project_client: form.client.trim(), accept_terms: true,
        terms_version: cfg.terms_version,
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
      <form onSubmit={submit} noValidate data-testid="license-modal">
        <p className="-mt-2 mb-4 text-sm text-slate-400">{track.artist_display_name}</p>
        {cfg.test_mode && (
          <p className="mb-4 rounded-xl border border-amber-400/30 bg-amber-400/[0.06] px-3 py-2 text-xs text-amber-100">
            Test mode (admins only). Pay with card 4242 4242 4242 4242, any future date, any CVC.
          </p>
        )}

        <fieldset className="space-y-2">
          <legend className="sr-only">License tier</legend>
          {cfg.tiers.map((t) => (
            <label key={t.id}
              className={`flex cursor-pointer items-center justify-between rounded-xl border px-3.5 py-2.5 ${t.id === tier ? 'border-electric-light bg-electric/[0.08]' : 'border-white/10'}`}>
              <span className="flex items-center gap-3">
                <input type="radio" name="tier" value={t.id} checked={t.id === tier} onChange={() => setTier(t.id)} className="accent-[#B44FD4]" />
                <span>
                  <span className="block text-sm text-white">{t.label}</span>
                  {t.description && <span className="block text-xs text-slate-500">{t.description}</span>}
                </span>
              </span>
              <b className="text-sm font-medium text-white">{fmtMoney(t.price_cents)}</b>
            </label>
          ))}
        </fieldset>

        {cfg.stems_available && (
          <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
            <input type="checkbox" checked={stems} onChange={(e) => setStems(e.target.checked)} className="mt-1 accent-[#B44FD4]" />
            <span>Add stems: vocals, instrumental, drums, bass, other
              <span className="ml-1.5 text-slate-500">+{fmtMoney(selected.price_with_stems_cents - selected.price_cents)}</span></span>
          </label>
        )}

        <div className="mt-4 space-y-3">
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

        <details className="mt-4 rounded-xl border border-white/10 px-3.5 py-2.5">
          <summary className="cursor-pointer text-sm text-cyan">Read the license terms ({cfg.terms_version})</summary>
          <div className="mt-2 max-h-48 space-y-2 overflow-y-auto text-xs leading-relaxed text-slate-400">
            {cfg.terms.map((p) => <p key={p}>{p}</p>)}
          </div>
        </details>
        <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
          <input type="checkbox" checked={agreed} onChange={(e) => { setAgreed(e.target.checked); setErrors({}); }} className="mt-1 accent-[#B44FD4]" />
          I agree to the license terms
        </label>
        {errors.terms && <p className="mt-1 text-xs text-red-300">{errors.terms}</p>}
        {errors.form && <p className="mt-3 rounded-xl border border-red-400/30 bg-red-400/[0.06] px-3 py-2 text-xs text-red-200">{errors.form}</p>}

        <div className="mt-5 flex gap-2.5">
          <button type="button" onClick={onClose} disabled={submitting}
            className="h-11 rounded-full border border-white/10 px-5 text-sm text-slate-300 hover:text-white disabled:opacity-50">Cancel</button>
          <button type="submit" disabled={submitting} data-testid="license-continue"
            className="flex h-11 flex-1 items-center justify-center gap-2 rounded-full bg-gradient-brand text-sm font-medium text-white disabled:opacity-60">
            {submitting ? <><Loader2 size={16} className="animate-spin" /> Opening checkout</> : <>Continue to payment · {fmtMoney(total)}</>}
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-slate-500">Tax is calculated at checkout. Payment is handled by Stripe.</p>
      </form>
    </Modal>
  );
};

export default LicenseModal;
