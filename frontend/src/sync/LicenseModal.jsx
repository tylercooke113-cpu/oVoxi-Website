import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import Modal from './Modal';
import { errorMessage, subscriptionsApi, accountApi } from './api';
import { checkoutApi, fmtMoney } from './checkout';
import { SUB_COPY } from './constants';
import QuoteForm from './QuoteForm';

// PRD-03 7.2 / Brief 18: single-track license tiers. Brief 19 adds the subscription plan path
// (register one project under the signed-in user's plan) above the single-track flow.

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const input = 'h-10 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm text-white placeholder:text-slate-600 focus:border-electric focus:outline-none';

// States with a usable plan path (brief item 3). "ended"/"none" show no plan path.
const PLAN_STATES = ['active', 'grace', 'ending', 'blocked_payment', 'blocked_dispute'];

const LIMITS = {
  creator: 'Your own channels only. No client work, sponsored content or paid ads. Perpetual for this project.',
  digital: 'Paid ads up to $25,000 total spend, running 12 months from the license date. Organic use is perpetual.',
  campaign: 'Up to $100,000 total media spend during the term, starting on the license date. Includes out-of-home, retail, events and trade shows.',
  broadcast: 'Ads: up to $250,000 spend for the term, starting on the license date, in one country. Programs and films: perpetual in that country, plus festivals worldwide.',
  enterprise: 'Tell us what you need and we will send a custom quote.',
  buyout: 'Exclusive sync rights for this track. Priced by quote. The track leaves the library during your exclusive term.',
};

// First of next month in UTC, as "Nov 1" (brief item 10.5 monthly-cap reset).
const nextMonthUtc = () => {
  const n = new Date();
  return new Date(Date.UTC(n.getUTCFullYear(), n.getUTCMonth() + 1, 1))
    .toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
};

const LicenseModal = ({ track, config, onClose, refreshConfig, getToken, isSignedIn }) => {
  const loc = useLocation();
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

  // Subscription plan path (Brief 19 item 10).
  const subsActive = isSignedIn && !!config.subscriptions_enabled;
  const [meState, setMeState] = useState(subsActive ? 'loading' : 'none'); // loading | ready | error | none
  const [me, setMe] = useState(null);
  const [mode, setMode] = useState('single');            // 'plan' | 'single'
  const singleTouchedRef = useRef(false);                // read live in the /me effect to avoid a stale closure
  const [planForm, setPlanForm] = useState({ project: '', client: '' });
  const [includeStems, setIncludeStems] = useState(true); // mockup default: checked
  const [planAgreed, setPlanAgreed] = useState(false);
  const [planErrors, setPlanErrors] = useState({});
  const [registering, setRegistering] = useState(false);
  const [registered, setRegistered] = useState(null);
  const [remaining, setRemaining] = useState(null);

  useEffect(() => {
    if (!subsActive) return undefined;
    let alive = true;
    subscriptionsApi.me(getToken)
      .then((data) => {
        if (!alive) return;
        setMe(data);
        setRemaining(Math.max((data.month_cap || 0) - (data.month_used || 0), 0));
        setMeState('ready');
        // Default to plan mode only if the single-license form is untouched (brief item 10.2).
        // Live ref read so a touch before /me resolves keeps single mode (no stale closure).
        if (data.subscription && data.can_register && PLAN_STATES.includes(data.state)
            && !singleTouchedRef.current) setMode('plan');
      })
      .catch(() => { if (alive) setMeState('error'); }); // /me failed: single license only
    return () => { alive = false; };
    // Fetch once when the modal opens (brief item 10.6).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isQuote = sel === 'enterprise' || sel === 'buyout';
  const tier = tierMap[sel];
  const hasTerms = !!tier?.terms;
  const needsTerritory = !!tier?.needs_territory;
  const touchSingle = () => { singleTouchedRef.current = true; };
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setErrors({}); touchSingle(); };

  const hasPlan = meState === 'ready' && !!me?.subscription && PLAN_STATES.includes(me.state);
  const planName = me?.subscription?.plan_label || '';
  const planMeta = useMemo(() => (cfg.plans || []).find((p) => p.id === me?.plan) || null, [cfg, me]);
  const resetDate = nextMonthUtc();

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
    setSel(id); setErrors({}); touchSingle();
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

  const bannerText = () => {
    if (!me.can_register) {
      if (me.reason === 'month_cap') return SUB_COPY.blockedMonthCap(planName, me.month_cap, resetDate);
      if (me.reason === 'day_cap') return SUB_COPY.blockedDayCap;
      if (me.reason === 'payment') return SUB_COPY.blockedPayment;
      if (me.reason === 'dispute') return SUB_COPY.blockedDispute;
    }
    return SUB_COPY.planBanner(planName, remaining, me.month_cap);
  };

  const registerProject = async (e) => {
    e.preventDefault();
    const next = {};
    if (!planForm.project.trim()) next.project = 'Name the project this license is for.';
    if (!planAgreed) next.terms = SUB_COPY.registerPublishError;
    if (Object.keys(next).length) { setPlanErrors(next); return; }
    setRegistering(true);                                  // disabled while the request runs
    try {
      const res = await subscriptionsApi.register(getToken, {
        track_id: track.id, project_name: planForm.project.trim(), project_client: planForm.client.trim(),
        include_stems: cfg.stems_available && includeStems, accept_terms: true, terms_version: cfg.terms_version,
      });
      setRegistered(res);
      setRemaining(res.remaining);                         // banner reflects remaining after register
    } catch (err) {
      setRegistering(false);
      if (err?.response?.status === 403) {
        // Cap/block hit on submit: re-sync /me so the banner shows the reason, then fall back to
        // the single-license path (always available), matching the mockup's capped screen.
        try {
          const data = await subscriptionsApi.me(getToken);
          setMe(data);
          setRemaining(Math.max((data.month_cap || 0) - (data.month_used || 0), 0));
          if (!data.can_register) setMode('single');
        } catch { /* keep the last banner */ }
        return;
      }
      setPlanErrors({ form: errorMessage(err, SUB_COPY.registerError) });
    }
  };

  const openCertificate = async () => {
    try {
      window.location.assign(await accountApi.certificate(getToken, registered.license_id));
    } catch (err) {
      setPlanErrors({ form: errorMessage(err, SUB_COPY.certificateError) });
    }
  };

  const busy = submitting || registering;

  return (
    <Modal open title={`License "${track.track_name}"`} onClose={busy ? () => {} : onClose}>
      <p className="-mt-2 mb-4 text-sm text-slate-400">{track.artist_display_name}</p>

      {!isSignedIn && config.subscriptions_enabled && (
        <p className="mb-4 rounded-xl border border-cyan/25 bg-cyan/[0.05] px-3 py-2 text-sm text-slate-300">
          Have a subscription? <Link to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} className="text-cyan hover:underline">Sign in</Link> to use this track with your plan.
        </p>
      )}

      {hasPlan && (
        <>
          <div className={`mb-3 rounded-xl border px-3.5 py-3 text-sm ${me.can_register ? 'border-electric-light/50 bg-electric/[0.07] text-slate-300' : 'border-amber-400/45 bg-amber-400/[0.06] text-amber-200'}`}>
            {bannerText()}
          </div>
          <div className="mb-1 flex gap-2.5">
            <button type="button" disabled={!me.can_register} onClick={() => { if (me.can_register) setMode('plan'); }}
              className={`flex-1 rounded-xl border px-3 py-2.5 text-left text-sm ${me.can_register ? 'cursor-pointer' : 'cursor-not-allowed opacity-40'} ${mode === 'plan' ? 'border-electric-light/70 bg-electric/[0.08] text-white' : 'border-white/10 text-slate-400'}`}>
              <b className="block font-medium">{SUB_COPY.choicePlan(planName)}</b>{SUB_COPY.choicePlanSub}
            </button>
            <button type="button" onClick={() => setMode('single')}
              className={`flex-1 cursor-pointer rounded-xl border px-3 py-2.5 text-left text-sm ${mode === 'single' ? 'border-electric-light/70 bg-electric/[0.08] text-white' : 'border-white/10 text-slate-400'}`}>
              <b className="block font-medium">{SUB_COPY.choiceSingle}</b>{SUB_COPY.choiceSingleSub}
            </button>
          </div>
        </>
      )}

      {mode === 'plan' && hasPlan ? (
        registered ? (
          <div className="py-4 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-brand text-2xl">✓</div>
            <h3 className="mb-1.5 text-lg font-semibold text-white">{SUB_COPY.doneTitle}</h3>
            <p className="text-sm text-slate-400">{SUB_COPY.doneBody(planForm.project.trim(), planName)}</p>
            <p className="mt-1 text-sm text-slate-400">{SUB_COPY.doneLicenseLine(registered.license_id)}</p>
            {planErrors.form && <p className="mt-3 text-xs text-red-300">{planErrors.form}</p>}
            <div className="mt-5 flex items-center justify-center gap-2.5">
              <button type="button" onClick={openCertificate} className="rounded-full border border-white/10 px-5 py-2 text-sm text-slate-200">{SUB_COPY.certificateButton}</button>
              <button type="button" onClick={() => window.location.assign(registered.download_url)} className="rounded-full bg-gradient-brand px-6 py-2.5 text-sm font-medium text-white">{SUB_COPY.downloadButton}</button>
            </div>
          </div>
        ) : (
          <form onSubmit={registerProject} noValidate className="mt-2">
            {planMeta && (
              <p className="rounded-xl border border-cyan/25 bg-cyan/[0.05] px-3 py-2 text-xs text-slate-300">{planMeta.scope_summary} {planMeta.term_label}</p>
            )}
            <div className="mt-3 space-y-3">
              <div>
                <label htmlFor="sub-project" className="mb-1 block text-xs text-slate-300">Project name</label>
                <input id="sub-project" className={input} value={planForm.project} maxLength={120}
                  onChange={(e) => { setPlanForm({ ...planForm, project: e.target.value }); setPlanErrors({}); }} placeholder="Summer campaign teaser" />
                {planErrors.project && <p className="mt-1 text-xs text-red-300">{planErrors.project}</p>}
              </div>
              <div>
                <label htmlFor="sub-client" className="mb-1 block text-xs text-slate-300">Client (optional)</label>
                <input id="sub-client" className={input} value={planForm.client} maxLength={120}
                  onChange={(e) => setPlanForm({ ...planForm, client: e.target.value })} placeholder="Acme Inc." />
              </div>
            </div>
            {cfg.stems_available && (
              <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
                <input type="checkbox" checked={includeStems} onChange={(e) => setIncludeStems(e.target.checked)} className="mt-1 accent-[#B44FD4]" />
                {SUB_COPY.includeStems}
              </label>
            )}
            <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
              <input type="checkbox" checked={planAgreed} onChange={(e) => { setPlanAgreed(e.target.checked); setPlanErrors({}); }} className="mt-1 accent-[#B44FD4]" />
              <span>I'll publish this project within 6 months, under the <a href={cfg.terms_url} target="_blank" rel="noreferrer" className="text-cyan hover:underline">oVoxi Music License Terms</a>.</span>
            </label>
            {planErrors.terms && <p className="mt-1 text-xs text-red-300">{planErrors.terms}</p>}
            {planErrors.form && <p className="mt-3 rounded-xl border border-red-400/30 bg-red-400/[0.06] px-3 py-2 text-xs text-red-200">{planErrors.form}</p>}
            <div className="mt-5 flex items-center justify-between gap-2.5">
              <span className="text-xs text-slate-500">{SUB_COPY.registerFootnote(remaining)}</span>
              <button type="submit" disabled={registering} className="flex h-11 items-center justify-center gap-2 rounded-full bg-gradient-brand px-6 text-sm font-medium text-white disabled:opacity-60">
                {registering ? <><Loader2 size={16} className="animate-spin" /> {SUB_COPY.registerBusy}</> : SUB_COPY.registerButton}
              </button>
            </div>
          </form>
        )
      ) : (
        <>
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
              <select id="lic-term" className={input} value={term} onChange={(e) => { setTerm(e.target.value); touchSingle(); }}>
                {tier.terms.map((t) => <option key={t.id} value={t.id}>{t.label} ({fmtMoney(t.price_cents)})</option>)}
              </select>
            </div>
          )}
          {needsTerritory && (
            <div className="mt-3">
              <label htmlFor="lic-terr" className="mb-1 block text-xs text-slate-300">Territory (one country)</label>
              <select id="lic-terr" className={input} value={territory} onChange={(e) => { setTerritory(e.target.value); touchSingle(); }}>
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
                  <input type="checkbox" checked={stems} onChange={(e) => { setStems(e.target.checked); touchSingle(); }} className="mt-1 accent-[#B44FD4]" />
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
                <input type="checkbox" checked={agreed} onChange={(e) => { setAgreed(e.target.checked); setErrors({}); touchSingle(); }} className="mt-1 accent-[#B44FD4]" />
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
        </>
      )}
    </Modal>
  );
};

export default LicenseModal;
