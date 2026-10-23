import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { Loader2 } from 'lucide-react';
import { publicApi } from './api';
import { NotFound } from './PublicPageParts';
import Modal from './Modal';
import SubscribeModal from './SubscribeModal';
import QuoteForm from './QuoteForm';
import { PRICING_COPY as C, AI_PRICING as AI } from './constants';

// Comma money, matching the approved pricing mockup ("$1,499", "$16.15", "$149").
const money = (cents) => {
  const d = (cents || 0) / 100;
  return '$' + d.toLocaleString('en-US', { minimumFractionDigits: d % 1 ? 2 : 0, maximumFractionDigits: 2 });
};

const Pill = ({ options, value, onChange }) => (
  <div className="inline-flex overflow-hidden rounded-full border border-white/10">
    {options.map(([v, label]) => (
      <button key={v} type="button" onClick={() => onChange(v)}
        className={`px-3.5 py-1.5 text-sm ${v === value ? 'bg-electric/[0.28] text-white' : 'text-slate-400'}`}>
        {label}
      </button>
    ))}
  </div>
);

const Cell = ({ v }) => {
  if (v === 'Y') return <span className="text-cyan">✓</span>;
  if (v === 'N') return <span className="text-slate-600">–</span>;
  return <span>{v}</span>;
};

const Feature = ({ children, no }) => (
  <li className={`flex gap-2 ${no ? 'text-slate-500' : 'text-slate-300'}`}>
    <span className={no ? 'text-slate-500' : 'text-cyan'} aria-hidden="true">{no ? '–' : '✓'}</span>
    <span>{children}</span>
  </li>
);

const CARD = 'relative flex flex-col rounded-2xl border p-6';
const GRID = { gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))' };

const PricingPage = () => {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [state, setState] = useState({ loading: true, error: false, data: null });
  const [ptype, setPtype] = useState('sub');
  const [bill, setBill] = useState('m');
  const [sub, setSub] = useState({ open: false, plan: null, interval: 'month' });
  const [quote, setQuote] = useState(false);
  const [quoteMsg, setQuoteMsg] = useState('');
  const [quoteKind, setQuoteKind] = useState('enterprise');
  const openQuote = useCallback((msg = '', kind = 'enterprise') => {
    setQuoteMsg(msg); setQuoteKind(kind); setQuote(true);
  }, []);

  useEffect(() => {
    if (!isLoaded) return undefined;
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: false }));
    publicApi.pricing(getToken, isSignedIn)
      .then((d) => alive && setState({ loading: false, error: false, data: d }))
      .catch(() => alive && setState({ loading: false, error: true, data: null }));
    return () => { alive = false; };
  }, [getToken, isSignedIn, isLoaded]);

  const data = state.data;
  const subsEnabled = !!data?.subscriptions_enabled;

  // Single-track only when subscriptions are off (B2).
  useEffect(() => { if (data && !subsEnabled) setPtype('single'); }, [data, subsEnabled]);

  const openSubscribe = useCallback((plan, intervalWord) => {
    if (isSignedIn) { setSub({ open: true, plan, interval: intervalWord }); return; }
    const next = `/pricing?subscribe=${plan}&interval=${intervalWord === 'year' ? 'y' : 'm'}`;
    navigate(`/signup?${new URLSearchParams({ as: 'buyer', next }).toString()}`);
  }, [isSignedIn, navigate]);

  // Returning from buyer sign-up: open the modal for the requested plan, then strip the params.
  useEffect(() => {
    if (!data || !subsEnabled || !isSignedIn) return;
    const plan = params.get('subscribe');
    if (!plan || !data.plans.some((p) => p.id === plan)) return;
    setSub({ open: true, plan, interval: params.get('interval') === 'y' ? 'year' : 'month' });
    const next = new URLSearchParams(params);
    next.delete('subscribe'); next.delete('interval');
    setParams(next, { replace: true });
  }, [data, subsEnabled, isSignedIn, params, setParams]);

  if (state.loading || !isLoaded) {
    return <div className="flex min-h-[60vh] items-center justify-center bg-ink"><Loader2 className="animate-spin text-electric" size={28} /></div>;
  }
  if (state.error || !data) {
    return <div className="flex min-h-[60vh] items-center justify-center bg-ink"><p className="text-sm text-red-400">Could not load pricing. Please try again.</p></div>;
  }
  if (!data.visible) return <NotFound />;

  const byId = Object.fromEntries(data.plans.map((p) => [p.id, p]));
  const singlesById = Object.fromEntries(data.singles.map((s) => [s.id, s]));
  const monthly = bill === 'm';

  const rows = C.table.rows.map((r) => {
    if (r[0] === 'Price') return ['Price', `${money(byId.creator?.month_cents)}/mo`, `${money(byId.pro?.month_cents)}/mo`,
      `${money(byId.business?.month_cents)}/mo`, `${money(singlesById.digital?.price_cents)} ${C.oneTime}`];
    if (r[0] === 'Projects') return ['Projects', C.table.projectsLabel(byId.creator?.month_cap),
      C.table.projectsLabel(byId.pro?.month_cap), C.table.projectsLabel(byId.business?.month_cap), C.table.projectsSingle];
    return r;
  });

  const subCard = (p) => {
    const copy = C.plans[p.id];
    if (!copy) return null;
    const hero = p.id === 'pro';
    const subline = monthly
      ? C.loyaltySubline(money(p.month_cents_loyalty15), money(p.month_cents_loyalty20))
      : C.annualSubline(money(Math.round(p.year_cents / 12)));
    return (
      <div key={p.id} className={`${CARD} ${hero ? 'border-electric-light/60 bg-electric/[0.06]' : 'border-white/10 bg-white/[0.02]'}`}>
        {hero && <span className="absolute -top-3 left-5 rounded-full bg-gradient-brand px-2.5 py-0.5 text-[11px] font-semibold tracking-wide">{C.mostPopular}</span>}
        <h3 className="font-heading text-xl font-semibold text-white">{p.label}</h3>
        <div className="min-h-[36px] text-[13px] text-slate-500">{copy.for}</div>
        <div className="mt-3.5 font-heading text-3xl font-extrabold text-white">
          {monthly ? money(p.month_cents) : money(p.year_cents)}<span className="text-sm font-normal text-slate-400">{monthly ? '/month' : '/year'}</span>
        </div>
        <div className="min-h-[34px] text-[12.5px] text-slate-500">{subline}</div>
        <ul className="my-4 flex-1 space-y-1.5 text-sm">
          {copy.features.map((f) => <Feature key={f}>{f}</Feature>)}
          {copy.notIncluded.map((f) => <Feature key={f} no>{f}</Feature>)}
        </ul>
        <button type="button" onClick={() => openSubscribe(p.id, monthly ? 'month' : 'year')}
          className="rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white">{C.subscribe}</button>
      </div>
    );
  };

  const singleCard = (s) => {
    const desc = C.singles[s.id];
    if (!desc) return null;
    const hero = s.id === C.heroSingle;
    return (
      <div key={s.id} className={`${CARD} ${hero ? 'border-electric-light/60 bg-electric/[0.06]' : 'border-white/10 bg-white/[0.02]'}`}>
        {hero && <span className="absolute -top-3 left-5 rounded-full bg-gradient-brand px-2.5 py-0.5 text-[11px] font-semibold tracking-wide">{C.mostPopular}</span>}
        <h3 className="font-heading text-xl font-semibold text-white">{s.label}</h3>
        <div className="mt-2 font-heading text-3xl font-extrabold text-white">
          {s.by_quote ? C.custom : money(s.price_cents)}{!s.by_quote && <span className="text-sm font-normal text-slate-400"> {C.oneTime}</span>}
        </div>
        <p className="mt-2 flex-1 text-[13.5px] leading-relaxed text-slate-300">{desc}</p>
        <div className="mt-4">
          <button type="button" onClick={() => (s.by_quote ? setQuote(true) : navigate('/catalog'))}
            className="rounded-full border border-white/10 px-5 py-2.5 text-sm text-slate-200">
            {s.by_quote ? C.requestQuote : C.browseLibrary}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-ink pb-24 pt-24" data-testid="pricing-page">
      <div className="mx-auto max-w-6xl px-4">
        <h1 className="text-center font-heading text-4xl font-extrabold text-white">{C.title}</h1>
        <p className="mx-auto mb-7 mt-2 max-w-[620px] text-center text-slate-400">{C.lead}</p>

        <div className="mb-7 flex flex-wrap justify-center gap-3">
          {subsEnabled && <Pill options={[['sub', C.typeSubscriptions], ['single', C.typeSingle]]} value={ptype} onChange={setPtype} />}
          {subsEnabled && ptype === 'sub' && <Pill options={[['m', C.billMonthly], ['y', C.billAnnual]]} value={bill} onChange={setBill} />}
        </div>

        {ptype === 'sub' ? (
          <>
            <div className="grid gap-3.5" style={GRID}>
              {data.plans.map(subCard)}
              <div className={`${CARD} border-white/10 bg-white/[0.02]`}>
                <h3 className="font-heading text-xl font-semibold text-white">{C.enterprisePlan.label}</h3>
                <div className="min-h-[36px] text-[13px] text-slate-500">{C.enterprisePlan.for}</div>
                <div className="mt-3.5 font-heading text-3xl font-extrabold text-white">{C.custom}</div>
                <div className="min-h-[34px] text-[12.5px] text-slate-500">{C.enterpriseSubline}</div>
                <ul className="my-4 flex-1 space-y-1.5 text-sm">
                  {C.enterprisePlan.features.map((f) => <Feature key={f}>{f}</Feature>)}
                </ul>
                <button type="button" onClick={() => openQuote()}
                  className="rounded-full border border-white/10 px-5 py-2.5 text-sm text-slate-200">{C.contactSales}</button>
              </div>
            </div>
            <p className="mt-4 text-center text-sm text-slate-400"><b className="font-medium text-white">{C.loyaltyNoteLead}</b>{C.loyaltyNoteRest}</p>
            <p className="mt-1.5 text-center text-sm text-slate-400">{C.stemsNote}</p>
          </>
        ) : (
          <>
            <div className="grid gap-3.5" style={GRID}>
              {data.singles.map(singleCard)}
            </div>
            <p className="mt-4 text-center text-sm text-slate-400">
              {C.singleNote}{' '}
              <button type="button" onClick={() => openQuote()} className="text-cyan">{C.requestQuote}</button>.
            </p>
          </>
        )}

        <h2 className="mt-14 text-center font-heading text-2xl font-semibold text-white">{C.tableHeading}</h2>
        <div className="mt-3.5 overflow-x-auto rounded-2xl border border-white/10">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border-b border-white/10 bg-[#0A0A0C] px-3.5 py-3 text-left font-medium text-white"> </th>
                {C.table.columns.map((c) => <th key={c} className="border-b border-white/10 bg-[#0A0A0C] px-3.5 py-3 font-medium text-white">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r[0]}>
                  <td className="whitespace-nowrap border-b border-white/10 px-3.5 py-2.5 text-left text-slate-300">{r[0]}</td>
                  {r.slice(1).map((c, i) => <td key={i} className="whitespace-nowrap border-b border-white/10 px-3.5 py-2.5 text-center text-slate-300"><Cell v={c} /></td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-center text-sm text-slate-400">{C.tableNote}</p>

        {/* Brief 25 Part E: AI training. Same visibility as this page (data.visible). */}
        <section className="mt-16" data-testid="ai-pricing">
          <h2 className="text-center font-heading text-3xl font-extrabold text-white">{AI.heading}</h2>
          <p className="mx-auto mb-7 mt-2 max-w-[640px] text-center text-slate-400">{AI.lead}</p>

          <div className="grid gap-3.5" style={GRID}>
            {AI.scopes.map((s) => (
              <div key={s.key} className={`${CARD} border-white/10 bg-white/[0.02]`}>
                <h3 className="font-heading text-xl font-semibold text-white">{s.key}</h3>
                <p className="mt-2 flex-1 text-[13.5px] leading-relaxed text-slate-300">{s.desc}</p>
                <button type="button" onClick={() => openQuote(`AI training: ${s.key}`, 'ai_training')}
                  className="mt-4 rounded-full border border-white/10 px-5 py-2.5 text-sm text-slate-200">{C.contactSales}</button>
              </div>
            ))}
          </div>
        </section>
      </div>

      <SubscribeModal open={sub.open} onClose={() => setSub((s) => ({ ...s, open: false }))}
        config={{ plans: data.plans }} getToken={getToken} plan={sub.plan} interval={sub.interval} />

      <Modal open={quote} title={C.requestQuote} onClose={() => setQuote(false)}>
        <QuoteForm kind={quoteKind} onDone={() => {}} message={quoteMsg} />
      </Modal>
    </div>
  );
};

export default PricingPage;
