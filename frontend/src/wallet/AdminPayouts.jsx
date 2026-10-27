import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { errorMessage } from '../sync/api';
import { adminWalletApi, money } from './api';

// Admin Payouts tab (Brief 27 Part C). Close month prepares; Approve and pay is Tyler's
// click, and pays each payee once even if clicked twice.
const lastMonth = () => {
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() - 1);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
};
const BTN = 'rounded-full px-4 py-2 text-sm font-semibold disabled:opacity-50';
const INPUT = 'rounded-lg border border-white/10 bg-black px-3 py-2 text-sm text-white';
const who = (t) => t.email || t.payee_key;

const Group = ({ title, rows, note }) => (
  <div>
    <h4 className="mb-1 text-sm font-semibold text-white">{title} ({rows.length})</h4>
    {note && <p className="mb-1 text-xs text-slate-500">{note}</p>}
    {rows.length > 0 && (
      <ul className="space-y-0.5 text-sm text-slate-300">
        {rows.map((t) => <li key={t.payee_key}>{who(t)}: {money(t.amount_cents)}</li>)}
      </ul>
    )}
  </div>
);

export default function AdminPayouts({ getToken }) {
  const [period, setPeriod] = useState(lastMonth());
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState('');
  const [hold, setHold] = useState({ track_id: '', reason: '' });
  const [exclusives, setExclusives] = useState([]);
  const [pay, setPay] = useState({ license: '', amount: '', fee: '0', tax: '0', received_at: '', reference: '' });

  const load = useCallback(() => {
    adminWalletApi.overview(getToken, period).then(setData).catch((e) => toast.error(errorMessage(e)));
  }, [getToken, period]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { adminWalletApi.exclusives(getToken).then(setExclusives).catch(() => {}); }, [getToken]);

  const act = async (name, fn, ok) => {
    setBusy(name);
    try { const r = await fn(); toast.success(ok(r)); load(); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(''); }
  };
  const closeMonth = () => act('close', () => adminWalletApi.close(getToken, period),
    (r) => `${data.period_label} closed: ${r.statements} statements, ${r.made_available} lines made available.`);
  const approve = () => {
    const total = money(data.preview.total_to_pay_cents);
    if (!window.confirm(`Pay ${data.preview.pay.length} payees ${total} through Stripe now?`)) return;
    act('pay', () => adminWalletApi.pay(getToken, period),
      (r) => `Paid ${r.paid.length} payees ${money(r.paid_total_cents)}.${r.failed.length ? ` ${r.failed.length} failed.` : ''}`);
  };
  const cents = (v) => Math.round(parseFloat(v || '0') * 100);
  const recordPayment = () => act('exclusive', () => adminWalletApi.recordPayment(getToken, pay.license, {
    amount_cents: cents(pay.amount), fee_cents: cents(pay.fee), tax_cents: cents(pay.tax),
    received_at: pay.received_at, reference: pay.reference,
  }), (r) => (r.duplicate ? 'Already recorded.' : `Recorded. Revenue Share ${money(r.revenue_share_cents)}.`));

  if (!data) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-electric" size={28} /></div>;
  const p = data.preview;
  const failed = (data.payouts || []).filter((x) => x.status === 'failed');

  return (
    <div className="space-y-8" data-testid="admin-payouts">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-slate-300">
          <span className="mb-1 block text-xs text-slate-500">Month</span>
          <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} className={INPUT} />
        </label>
        <span className={`rounded-full px-3 py-1 text-xs ${data.livemode ? 'bg-green-400/10 text-green-400' : 'bg-amber-400/10 text-amber-300'}`}>
          {data.livemode ? 'Stripe live mode' : 'Stripe test mode'}
        </span>
      </div>

      <div className="rounded-xl border border-amber-400/35 bg-amber-400/[0.06] p-4 text-sm text-amber-100" data-testid="payout-deadline">
        Payments for {data.period_label} are due by {new Date(`${data.payment_due}T12:00:00Z`).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}.
        {data.december && ' December run: balances under $25 are paid too.'}
      </div>

      <section className="space-y-3">
        <h3 className="font-heading text-lg font-semibold text-white">1. Close month</h3>
        <p className="text-sm text-slate-400">
          {data.closed ? `Closed ${new Date(data.closed.closed_at).toLocaleString()} by ${data.closed.closed_by}. Pool ${money(data.closed.pool?.pool_cents)} over ${data.closed.pool?.projects || 0} Registered Projects. Closing again is safe.`
            : 'Builds the subscription Artist Pool, makes the month\'s earnings available, writes statements and emails co-owners without accounts. Pays nothing.'}
        </p>
        <button type="button" onClick={closeMonth} disabled={!!busy} className={`${BTN} border border-white/20 text-white hover:bg-white/10`}>
          {busy === 'close' ? 'Closing…' : `Close ${data.period_label}`}
        </button>
      </section>

      <section className="space-y-4">
        <h3 className="font-heading text-lg font-semibold text-white">2. Approve and pay</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <Group title="Will be paid" rows={p.pay} />
          <Group title="Below $25 (rolls over)" rows={p.below_minimum} />
          <Group title="Not verified yet (accrues)" rows={p.not_verified} />
          <Group title="No Wallet account yet" rows={p.no_account} note="Co-owners invited by email who have not signed up." />
          <Group title="Country not supported yet" rows={p.unsupported} />
          <Group title="Negative balance" rows={p.negative} note="A refund after a payout. Recovered from later earnings." />
        </div>
        {failed.length > 0 && (
          <div className="rounded-xl border border-red-400/30 bg-red-400/[0.06] p-3 text-sm text-red-200">
            {failed.map((f) => <div key={f.id}>{f.payee_key}: {money(f.amount_cents)} failed. {f.error}</div>)}
          </div>
        )}
        <button type="button" onClick={approve} disabled={!!busy || !data.closed || !p.pay.length}
          className={`${BTN} bg-gradient-brand text-white`} data-testid="payout-approve">
          {busy === 'pay' ? 'Paying…' : `Approve and pay ${money(p.total_to_pay_cents)}`}
        </button>
        {!data.closed && <p className="text-xs text-slate-500">Close the month first.</p>}
      </section>

      <section className="space-y-3">
        <h3 className="font-heading text-lg font-semibold text-white">Record an exclusive license payment</h3>
        <p className="text-sm text-slate-400">Money received outside checkout. Credits 40% of Net Revenue to the song's payees.</p>
        <div className="flex flex-wrap gap-2">
          <select value={pay.license} onChange={(e) => setPay({ ...pay, license: e.target.value })} className={INPUT}>
            <option value="">Choose a license</option>
            {exclusives.map((l) => <option key={l.id} value={l.id}>{l.track_title || l.track_id} · {(l.uses || []).join(' + ')}</option>)}
          </select>
          <input placeholder="Amount received ($)" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} className={INPUT} inputMode="decimal" />
          <input placeholder="Fees ($)" value={pay.fee} onChange={(e) => setPay({ ...pay, fee: e.target.value })} className={INPUT} inputMode="decimal" />
          <input placeholder="Tax ($)" value={pay.tax} onChange={(e) => setPay({ ...pay, tax: e.target.value })} className={INPUT} inputMode="decimal" />
          <input type="date" value={pay.received_at} onChange={(e) => setPay({ ...pay, received_at: e.target.value })} className={INPUT} />
          <input placeholder="Invoice or wire reference" value={pay.reference} onChange={(e) => setPay({ ...pay, reference: e.target.value })} className={INPUT} />
          <button type="button" onClick={recordPayment} disabled={!!busy || !pay.license || !pay.amount || !pay.received_at || !pay.reference}
            className={`${BTN} border border-white/20 text-white hover:bg-white/10`}>Record payment</button>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="font-heading text-lg font-semibold text-white">Holds for claims (Agreement 8.5)</h3>
        <div className="flex flex-wrap gap-2">
          <input placeholder="Track ID" value={hold.track_id} onChange={(e) => setHold({ ...hold, track_id: e.target.value })} className={INPUT} />
          <input placeholder="Reason" value={hold.reason} onChange={(e) => setHold({ ...hold, reason: e.target.value })} className={`${INPUT} min-w-[16rem]`} />
          <button type="button" disabled={!!busy || !hold.track_id || hold.reason.length < 3}
            onClick={() => act('hold', () => adminWalletApi.hold(getToken, hold), () => 'Track held.')}
            className={`${BTN} border border-white/20 text-white hover:bg-white/10`}>Hold</button>
        </div>
        {(data.holds || []).map((h) => (
          <div key={h.track_id} className="flex items-center gap-3 text-sm text-slate-300">
            <span>{h.track_id}: {h.reason}</span>
            <button type="button" onClick={() => act('release', () => adminWalletApi.release(getToken, h.track_id), () => 'Hold released.')}
              className="text-cyan hover:underline">Release</button>
          </div>
        ))}
      </section>
    </div>
  );
}
