import React, { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import Modal from './Modal';
import { startSubscriptionCheckout, errorMessage } from './api';
import { fmtMoney } from './checkout';
import { SUB_COPY } from './constants';

// Brief 19 item 12: the subscribe pop-up (#subm in pricing-licensing-mockup.html).
// Props-only so Brief 20's Pricing page can reuse it unchanged:
//   open, onClose, config (carries config.plans), getToken, optional plan, optional interval.
// With a `plan` prop it renders exactly the mockup (one plan). Without one (Account "Choose a
// plan") it adds a compact Creator / Pro / Business picker, Pro preselected. Names, prices and
// caps come from config.plans; no copy or discount math lives here.

const DEFAULT_PLAN = 'pro';

const SubscribeModal = ({ open, onClose, config, getToken, plan, interval }) => {
  const plans = useMemo(() => config?.plans || [], [config]);
  const planGiven = !!plan;
  const [sel, setSel] = useState(plan || DEFAULT_PLAN);
  const [sb, setSb] = useState(interval || 'month');
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  const meta = useMemo(() => plans.find((p) => p.id === sel) || null, [plans, sel]);

  // The component stays mounted while closed, so reset every time it opens. Without this,
  // Brief 20's Pricing page would reopen showing the previous plan and a pre-ticked agree box.
  useEffect(() => {
    if (open) { setSel(plan || DEFAULT_PLAN); setSb(interval || 'month'); setAgreed(false); setNotice(''); setBusy(false); }
  }, [open, plan, interval]);

  if (!open) return null;

  const title = SUB_COPY.subscribeTitle(meta?.label || '');

  const go = async () => {
    setBusy(true); setNotice('');
    try {
      const res = await startSubscriptionCheckout(getToken, { plan: sel, interval: sb });
      if (res.status === 'already_subscribed') { setBusy(false); setNotice(res.message); }
      // 'redirecting' leaves the page, so no further state change is needed.
    } catch (err) {
      setBusy(false);
      setNotice(errorMessage(err, 'Could not start checkout. Try again.'));
    }
  };

  if (!meta) {
    return (
      <Modal open title="Subscribe" onClose={onClose}>
        <p className="text-sm text-slate-400">Plans are temporarily unavailable. Please try again in a moment.</p>
      </Modal>
    );
  }

  const billRows = [
    { v: 'month', label: SUB_COPY.billingMonthly, price: SUB_COPY.priceMonth(fmtMoney(meta.month_cents)) },
    { v: 'year', label: SUB_COPY.billingAnnual, price: SUB_COPY.priceYear(fmtMoney(meta.year_cents)) },
  ];

  return (
    <Modal open title={title} onClose={busy ? () => {} : onClose}>
      <p className="-mt-2 mb-4 text-sm text-slate-400">{SUB_COPY.subscribeSubtitle}</p>

      {!planGiven && (
        <>
          <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">Plan</div>
          <div className="mb-4 flex gap-2">
            {plans.map((p) => (
              <button type="button" key={p.id} onClick={() => setSel(p.id)}
                className={`flex-1 rounded-xl border px-3 py-2.5 text-left text-sm ${p.id === sel ? 'border-electric-light/70 bg-electric/[0.08] text-white' : 'border-white/10 text-slate-400'}`}>
                <b className="block font-medium">{p.label}</b>
                <span className="text-xs text-slate-500">{SUB_COPY.priceMonth(fmtMoney(p.month_cents))}</span>
              </button>
            ))}
          </div>
        </>
      )}

      <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">Billing</div>
      <div className="space-y-2">
        {billRows.map((r) => (
          <label key={r.v}
            className={`flex cursor-pointer items-center justify-between rounded-xl border px-3.5 py-3 text-sm ${r.v === sb ? 'border-electric-light/70 bg-electric/[0.08] text-white' : 'border-white/10 text-slate-300'}`}>
            <span className="flex items-center gap-3">
              <input type="radio" name="sub-bill" checked={r.v === sb} onChange={() => setSb(r.v)} className="accent-[#B44FD4]" />
              <b className="font-medium">{r.label}</b>
            </span>
            <span className="font-medium">{r.price}</span>
          </label>
        ))}
      </div>

      <p className="mt-3 rounded-xl border border-cyan/25 bg-cyan/[0.05] px-3 py-2.5 text-xs text-slate-300">
        {sb === 'month'
          ? SUB_COPY.subscribeLoyaltyMonthly(fmtMoney(meta.month_cents), fmtMoney(meta.month_cents_loyalty15), fmtMoney(meta.month_cents_loyalty20))
          : SUB_COPY.subscribeLoyaltyAnnual(fmtMoney(meta.year_cents))}
      </p>

      <ul className="mt-3 list-disc space-y-1.5 pl-5 text-xs leading-relaxed text-slate-400">
        <li>{SUB_COPY.subscribeBullets[0]}</li>
        <li>{SUB_COPY.subscribeBullets[1]}</li>
        <li>{SUB_COPY.subscribeDownloadsBullet(meta.month_cap)}</li>
        <li>{SUB_COPY.subscribeBullets[2]}</li>
      </ul>

      <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-1 accent-[#B44FD4]" />
        <span>{SUB_COPY.subscribeAgree}</span>
      </label>

      {notice && <p className="mt-3 rounded-xl border border-amber-400/30 bg-amber-400/[0.06] px-3 py-2 text-xs text-amber-200">{notice}</p>}

      <div className="mt-5 flex items-center justify-between gap-2.5">
        <span className="text-sm text-slate-400">
          {SUB_COPY.subscribeTotal(fmtMoney(sb === 'month' ? meta.month_cents : meta.year_cents))} <span className="text-xs text-slate-500">{SUB_COPY.taxSuffix}</span>
        </span>
        <button type="button" disabled={!agreed || busy} onClick={go}
          className="flex h-11 items-center justify-center gap-2 rounded-full bg-gradient-brand px-6 text-sm font-medium text-white disabled:opacity-40">
          {busy ? <><Loader2 size={16} className="animate-spin" /> Opening checkout</> : SUB_COPY.subscribeButton}
        </button>
      </div>
    </Modal>
  );
};

export default SubscribeModal;
