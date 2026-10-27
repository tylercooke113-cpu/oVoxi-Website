import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { errorMessage } from '../sync/api';
import { money, walletApi } from './api';

// The OVOXI Wallet in the Vault (Brief 27 Part D). A ledger and statement view: balances
// cannot be spent or transferred here (Artist Agreement 8.1).
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const FIELD = { sync: 'Sync', ai: 'AI training', 'ai+sync': 'Sync and AI training' };
const STATUS = { accrued: 'Pending', available: 'Available', in_payout: 'Paying', paid: 'Paid', held: 'Held' };

const Stat = ({ label, value, note, testid }) => (
  <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4" data-testid={testid}>
    <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
    <div className="mt-1 font-heading text-2xl font-semibold text-white">{value}</div>
    {note && <div className="mt-0.5 text-xs text-slate-500">{note}</div>}
  </div>
);

function PayoutSetup({ getToken, connect, onChanged }) {
  const [status, setStatus] = useState(null);
  const [country, setCountry] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    walletApi.status(getToken).then((s) => { setStatus(s); setCountry(s.country || s.suggested_country || ''); })
      .catch(() => setStatus({ countries: [] }));
  }, [getToken]);

  const start = async () => {
    if (!country) { toast.error('Choose the country of your bank account.'); return; }
    setBusy(true);
    try {
      const res = await walletApi.connect(getToken, country);
      if (res.url) { window.location.assign(res.url); return; }
      toast.message(res.message);
      onChanged();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const dashboard = async () => {
    try { window.location.assign(await walletApi.dashboard(getToken)); } catch (e) { toast.error(errorMessage(e)); }
  };

  if (connect?.unsupported) {
    return <p className="text-sm text-amber-200" data-testid="wallet-unsupported">{connect.message}</p>;
  }
  if (connect?.payouts_enabled) {
    return (
      <div className="flex flex-wrap items-center gap-3" data-testid="wallet-verified">
        <span className="rounded-full border border-green-400/25 bg-green-400/[0.08] px-3 py-1 text-xs font-medium text-green-400">Verified, payouts on</span>
        <button type="button" onClick={dashboard} className="text-sm text-slate-300 underline hover:text-white">View payouts and tax forms in Stripe</button>
      </div>
    );
  }
  if (connect?.connected) {
    return (
      <div className="flex flex-wrap items-center gap-3" data-testid="wallet-action-needed">
        <span className="rounded-full border border-amber-400/25 bg-amber-400/[0.08] px-3 py-1 text-xs font-medium text-amber-300">Action needed</span>
        <button type="button" onClick={start} disabled={busy}
          className="rounded-full bg-gradient-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          {busy ? 'Opening…' : 'Finish setup with Stripe'}
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-end gap-3" data-testid="wallet-connect">
      <label className="text-sm text-slate-300">
        <span className="mb-1 block text-xs text-slate-500">Country of your bank account</span>
        <select value={country} onChange={(e) => setCountry(e.target.value)} data-testid="wallet-country"
          className="rounded-lg border border-white/10 bg-black px-3 py-2 text-sm text-white">
          <option value="">Choose a country</option>
          {(status?.countries || []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          <option value="XX">Another country</option>
        </select>
      </label>
      <button type="button" onClick={start} disabled={busy} data-testid="wallet-connect-button"
        className="rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
        {busy ? 'Opening…' : 'Connect your bank account'}
      </button>
    </div>
  );
}

export default function WalletTab({ getToken }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    walletApi.me(getToken).then(setData).catch(() => setError(true));
  }, [getToken]);
  useEffect(() => { load(); }, [load]);

  const download = async (period) => {
    try { window.open(await walletApi.statement(getToken, period), '_blank', 'noopener'); }
    catch (e) { toast.error(errorMessage(e)); }
  };

  if (error) return <p className="py-10 text-center text-slate-400">Could not load your Wallet. Refresh to try again.</p>;
  if (!data) return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-electric" size={32} /></div>;
  const s = data.summary;

  return (
    <div className="space-y-8" data-testid="wallet-tab">
      <p className="text-sm text-slate-400">
        Your OVOXI Wallet shows what you have earned. Payments go to your bank account monthly. Balances under
        {' '}{money(data.minimum_cents)} roll over to the next month.
        {data.test_mode && <span className="ml-2 rounded-full border border-amber-400/30 px-2 py-0.5 text-xs text-amber-300">Test mode</span>}
      </p>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Earned this month" value={money(s.earned_this_month_cents)} testid="wallet-earned" />
        <Stat label="Available" value={money(s.available_cents)} note="Paid in the next payout" testid="wallet-available" />
        <Stat label="Held" value={money(s.held_cents)} note={s.held_cents ? 'Held while a claim is reviewed' : undefined} testid="wallet-held" />
        <Stat label="Paid to date" value={money(s.paid_cents)} testid="wallet-paid" />
      </div>

      <section>
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Payout setup</h3>
        <PayoutSetup getToken={getToken} connect={data.connect} onChanged={load} />
      </section>

      <section>
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Earnings</h3>
        {data.entries.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-400">
            No earnings yet. When one of your songs is licensed, your share shows up here.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-sm" data-testid="wallet-entries">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>{['Date', 'Song', 'Type', 'Your share', 'Amount', 'Status'].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {data.entries.map((e) => (
                  <tr key={e.id} className="border-t border-white/5 text-slate-300">
                    <td className="px-4 py-2.5 whitespace-nowrap">{fmtDate(e.date)}</td>
                    <td className="px-4 py-2.5 text-white">{e.track_title}{e.test_mode && <span className="ml-1 text-xs text-amber-300">(test)</span>}</td>
                    <td className="px-4 py-2.5">{e.kind}{e.field && e.kind !== 'Refund' && e.kind !== 'Chargeback' ? ` (${FIELD[e.field] || e.field})` : ''}</td>
                    <td className="px-4 py-2.5">{e.share_bp ? `${e.share_bp / 100}%` : ''}</td>
                    <td className={`px-4 py-2.5 whitespace-nowrap ${e.amount_cents < 0 ? 'text-red-300' : 'text-white'}`}>{money(e.amount_cents)}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-400">{STATUS[e.status] || e.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Statements</h3>
        {data.statements.length === 0 ? (
          <p className="text-sm text-slate-400">Your first statement appears after the month you first earn in.</p>
        ) : (
          <ul className="divide-y divide-white/5 rounded-2xl border border-white/10" data-testid="wallet-statements">
            {data.statements.map((st) => (
              <li key={st.period} className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="text-white">{st.period_label}</span>
                <span className="text-slate-400">{money(st.revenue_share_cents)}</span>
                <button type="button" onClick={() => download(st.period)} className="text-cyan hover:underline">Download PDF</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
