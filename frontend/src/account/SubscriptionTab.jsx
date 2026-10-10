import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { subscriptionsApi, errorMessage } from '../sync/api';
import { fmtMoney, useCheckoutConfig } from '../sync/checkout';
import SubscribeModal from '../sync/SubscribeModal';
import {
  SUB_COPY, SUB_STATUS_LABELS,
  SUB_POLL_INTERVAL_MS, SUB_POLL_TIMEOUT_MS, SUB_POLLING_COPY, SUB_POLL_TIMEOUT_COPY,
} from '../sync/constants';

// Brief 19 item 11: the Account "Subscription" tab (mockup screens 2 to 4 in
// subscriptions-mockup-1.html, plus the brief's no-plan case). All money, dates and loyalty
// figures come pre-computed from GET /api/subscriptions/me; this file only formats and lays out.

// "Aug 4, 2026".
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '');
// "Oct 12" (mockup grace/ending chip drop the year).
const fmtShort = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '');
const ordinal = (n) => {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
};
// A subscription has settled (webhook mirrored) once it reaches one of these states.
const SETTLED = ['active', 'ending', 'grace'];

const Chip = ({ className, children }) => (
  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}>{children}</span>
);
const Field = ({ label, children }) => (
  <div>
    <span className="block text-[11px] uppercase tracking-wide text-slate-500">{label}</span>
    {children}
  </div>
);
const Meter = ({ used, cap }) => (
  <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-800">
    <div className="h-full bg-gradient-brand" style={{ width: `${Math.min(100, Math.round(((used || 0) / (cap || 1)) * 100))}%` }} />
  </div>
);

export default function SubscriptionTab({ getToken, onViewProjects }) {
  const { config } = useCheckoutConfig();
  const [params, setParams] = useSearchParams();
  const [me, setMe] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [polling, setPolling] = useState(false);
  const [pollTimedOut, setPollTimedOut] = useState(false);
  const [busy, setBusy] = useState(false);
  const [subOpen, setSubOpen] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let alive = true;
    const cameFromCheckout = params.get('checkout') === 'success';
    const deadline = Date.now() + SUB_POLL_TIMEOUT_MS;
    const tick = async () => {
      try {
        const data = await subscriptionsApi.me(getToken);
        if (!alive) return;
        setMe(data);
        setLoaded(true);
        const settled = !!data.subscription && SETTLED.includes(data.state);
        if (cameFromCheckout && !settled && Date.now() < deadline) {
          setPolling(true);
          setTimeout(tick, SUB_POLL_INTERVAL_MS);
        } else {
          setPolling(false);
          if (cameFromCheckout && !settled) setPollTimedOut(true);
          if (cameFromCheckout && settled) {
            const next = new URLSearchParams(params);
            next.delete('checkout');
            setParams(next, { replace: true });
          }
        }
      } catch {
        if (alive) { setLoaded(true); setPolling(false); }
      }
    };
    tick();
    return () => { alive = false; };
    // Fetch once when the tab mounts; poll only when returning from Stripe Checkout.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reload = async () => {
    try { setMe(await subscriptionsApi.me(getToken)); }
    catch (e) { toast.error(errorMessage(e)); }
  };

  const toPortal = async () => {
    setBusy(true);
    try { window.location.assign(await subscriptionsApi.portal(getToken)); }
    catch (e) { setBusy(false); toast.error(errorMessage(e)); }
  };

  const keepPlan = async () => {
    setBusy(true);
    try { await subscriptionsApi.resume(getToken); await reload(); toast.success('Your plan is active again.'); }
    catch (e) { toast.error(errorMessage(e)); }
    finally { setBusy(false); }
  };

  if (!loaded) {
    return <div className="mt-6 flex justify-center py-10"><Loader2 className="animate-spin text-electric" size={28} /></div>;
  }
  if (polling) {
    return (
      <div className="mt-6 flex items-center justify-center gap-3 rounded-2xl border border-white/10 p-7 text-sm text-slate-300">
        <Loader2 className="animate-spin text-electric" size={20} /> {SUB_POLLING_COPY}
      </div>
    );
  }

  const state = me?.state || 'none';
  const sub = me?.subscription;
  const planLabel = sub?.plan_label || '';
  const planMeta = (config?.plans || []).find((p) => p.id === me?.plan) || null;
  const isMonthly = sub?.interval === 'month';
  const intervalWord = isMonthly ? 'monthly' : 'annual';
  const price = sub ? fmtMoney(sub.price_cents) : '';
  const fullPrice = planMeta ? fmtMoney(planMeta.month_cents) : price;

  // No plan (or ended): the only call to action is to subscribe. Brief item 11 no-plan case.
  if (!sub || state === 'none' || state === 'ended') {
    return (
      <>
        <div className="mt-5 rounded-2xl border border-dashed border-white/10 p-7 text-center text-slate-400">
          <p className="mb-1.5 font-medium text-white">{SUB_COPY.noPlan}</p>
          {state === 'ended' && <p className="mb-2 text-sm">{SUB_COPY.planEnded}</p>}
          {pollTimedOut && <p className="mb-2 text-sm text-amber-300">{SUB_POLL_TIMEOUT_COPY}</p>}
          <button type="button" onClick={() => setSubOpen(true)}
            className="mt-2 inline-block rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white">{SUB_COPY.noPlanButton}</button>
        </div>
        <SubscribeModal open={subOpen} onClose={() => setSubOpen(false)} config={config} getToken={getToken} />
      </>
    );
  }

  const loyaltyNote = () => {
    if (!isMonthly) return <>{SUB_COPY.loyaltyAnnualTab}</>;
    const body = sub.loyalty_pct >= 20
      ? SUB_COPY.loyaltyAt20
      : SUB_COPY.loyaltyBefore20(fmtMoney(sub.next_loyalty_price_cents), ordinal(sub.next_loyalty_month), fmtDate(sub.next_loyalty_date));
    return <><b className="font-medium text-white">{SUB_COPY.loyaltyLabel}</b> {body} {SUB_COPY.loyaltyTail(fullPrice)}</>;
  };

  // Payment failed (grace, or blocked after the grace window): mockup "pastdue" screen.
  if (state === 'grace' || state === 'blocked_payment') {
    return (
      <div className="mt-5">
        <div className="mb-4 rounded-xl border border-amber-400/35 bg-amber-400/[0.06] px-3.5 py-3 text-sm text-amber-200">
          {SUB_COPY.graceWarning(fmtShort(sub.grace_ends_at))}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-heading text-xl font-semibold text-white">{SUB_COPY.planHeading(planLabel, intervalWord)}</h3>
              <div className="mt-0.5 text-sm text-slate-400">{SUB_COPY.memberSince(fmtDate(sub.subscribed_since))}</div>
            </div>
            <Chip className="text-amber-300 border-amber-400/25 bg-amber-400/[0.08]">{SUB_STATUS_LABELS.past_due}</Chip>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3.5 text-sm sm:grid-cols-3">
            <Field label={SUB_COPY.fieldAmountDue}>{price}</Field>
            <Field label={SUB_COPY.fieldDownloads}>{SUB_COPY.downloadsAvailableUntil(fmtShort(sub.grace_ends_at))}</Field>
            <Field label={SUB_COPY.fieldRegisteredProjects}>{me.registered_count}</Field>
          </div>
          <div className="mt-5">
            <button type="button" disabled={busy} onClick={toPortal}
              className="rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{SUB_COPY.graceButton}</button>
          </div>
        </div>
      </div>
    );
  }

  // Cancelled, ends at period end: mockup "ending" screen.
  if (state === 'ending') {
    return (
      <div className="mt-5">
        <div className="mb-4 rounded-xl border border-cyan/25 bg-cyan/[0.05] px-3.5 py-3 text-sm text-slate-300">
          {SUB_COPY.endingInfo(fmtDate(sub.next_payment_date))}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-heading text-xl font-semibold text-white">{SUB_COPY.planHeading(planLabel, intervalWord)}</h3>
              <div className="mt-0.5 text-sm text-slate-400">{SUB_COPY.memberSince(fmtDate(sub.subscribed_since))}</div>
            </div>
            <Chip className="text-slate-300 border-white/10">{SUB_STATUS_LABELS.ending(fmtShort(sub.next_payment_date))}</Chip>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3.5 text-sm sm:grid-cols-3">
            <Field label={SUB_COPY.fieldDownloadsThisMonth}>{me.month_used} of {me.month_cap}<Meter used={me.month_used} cap={me.month_cap} /></Field>
            <Field label={SUB_COPY.fieldRegisteredProjects}>{me.registered_count}</Field>
          </div>
          <p className="mt-4 text-sm text-slate-400">{SUB_COPY.endingNote(fmtDate(sub.next_payment_date))}</p>
          <div className="mt-5">
            <button type="button" disabled={busy} onClick={keepPlan}
              className="rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{SUB_COPY.endingButton}</button>
          </div>
        </div>
      </div>
    );
  }

  // Active (and blocked_dispute, which is active with downloads paused): mockup "active" screen.
  return (
    <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
      {state === 'blocked_dispute' && (
        <div className="mb-4 rounded-xl border border-amber-400/35 bg-amber-400/[0.06] px-3.5 py-3 text-sm text-amber-200">{SUB_COPY.blockedDispute}</div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-heading text-xl font-semibold text-white">{SUB_COPY.planHeading(planLabel, intervalWord)}</h3>
          <div className="mt-0.5 text-sm text-slate-400">{SUB_COPY.memberSince(fmtDate(sub.subscribed_since))}</div>
        </div>
        <Chip className="text-green-400 border-green-400/25 bg-green-400/[0.08]">{SUB_STATUS_LABELS.active}</Chip>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3.5 text-sm sm:grid-cols-4">
        <Field label={SUB_COPY.fieldCurrentPrice}>
          {price} / {isMonthly ? 'month' : 'year'}
          {isMonthly && sub.loyalty_pct > 0 && <span className="ml-1 text-xs text-slate-400">{SUB_COPY.loyaltyPct(sub.loyalty_pct)}</span>}
        </Field>
        <Field label={SUB_COPY.fieldNextPayment}>{fmtDate(sub.next_payment_date)}</Field>
        <Field label={SUB_COPY.fieldDownloadsThisMonth}>{me.month_used} of {me.month_cap}<Meter used={me.month_used} cap={me.month_cap} /></Field>
        <Field label={SUB_COPY.fieldRegisteredProjects}>{me.registered_count}</Field>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-slate-400">{loyaltyNote()}</p>
      <div className="mt-5 flex flex-wrap items-center gap-2.5">
        <button type="button" disabled={busy} onClick={toPortal}
          className="rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{SUB_COPY.manageBilling}</button>
        <button type="button" onClick={onViewProjects}
          className="rounded-full border border-white/10 px-5 py-2.5 text-sm text-slate-300 hover:text-white">{SUB_COPY.viewProjects}</button>
      </div>
    </div>
  );
}
