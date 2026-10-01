import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { api, errorMessage } from './api';

// Admin orders (PRD-03 9): filters, CSV for manual payouts, resend email, reissue link.
// Every action is logged server-side in admin_actions.

const TIERS = { creator: 'Creator', creator_pro: 'Creator Pro', business_social: 'Business Social' };
const STATUSES = ['fulfilled', 'paid', 'pending', 'failed', 'refunded'];
const BADGE = {
  fulfilled: 'bg-cyan/10 text-sky-300', failed: 'bg-red-400/10 text-red-300',
  refunded: 'bg-amber-400/10 text-amber-200', paid: 'bg-white/10 text-slate-300', pending: 'bg-white/10 text-slate-300',
};
const money = (c) => (c == null ? '' : `$${(c / 100).toFixed(2)}`);
const day = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const field = 'h-9 rounded-xl border border-white/10 bg-white/[0.04] px-2.5 text-xs text-white focus:border-electric focus:outline-none';
const pill = 'rounded-full border border-white/15 px-3 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50';

const AdminOrdersSection = ({ getToken }) => {
  const [filters, setFilters] = useState({ status: '', artist: '', date_from: '', date_to: '', include_test: false });
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState('');
  const [reissued, setReissued] = useState(null);

  const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '' && v !== false));

  const load = useCallback(async () => {
    try { setData(await api.adminOrders(getToken, params)); } catch (err) { toast.error(errorMessage(err)); setData({ orders: [], artists: [] }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken, JSON.stringify(params)]);

  useEffect(() => { load(); }, [load]);

  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  const downloadCsv = async () => {
    setBusy('csv');
    try {
      const blob = await api.adminOrdersCsv(getToken, params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ovoxi-orders-${filters.date_from || 'all'}-to-${filters.date_to || 'now'}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) { toast.error(errorMessage(err, 'Could not export the CSV.')); } finally { setBusy(''); }
  };

  const resend = async (o) => {
    setBusy(o.order_id);
    try {
      const r = await api.adminResendEmail(getToken, o.order_id);
      if (r.email_status === 'sent') toast.success(`License email resent to ${o.buyer_email}.`);
      else toast.error(`Email ${r.email_status}${r.email_error ? `: ${r.email_error}` : ''}`);
      await load();
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(''); }
  };

  const reissue = async (o) => {
    if (!window.confirm(`Reissue the download link for ${o.license_id}? The current link stops working and the buyer is emailed the new one.`)) return;
    setBusy(o.order_id);
    try {
      const r = await api.adminReissueLink(getToken, o.order_id, true);
      setReissued({ license_id: o.license_id, url: r.download_url, email: r.email_status });
      await load();
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(''); }
  };

  const copy = async (text) => {
    try { await navigator.clipboard.writeText(text); toast.success('Link copied.'); } catch { toast.error('Copy failed. Select the link and copy it.'); }
  };

  return (
    <section data-testid="admin-orders">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="font-heading text-lg font-semibold text-white">Orders</h3>
        <button type="button" onClick={downloadCsv} disabled={busy === 'csv'}
          className="inline-flex items-center gap-1.5 rounded-full bg-gradient-brand px-4 py-1.5 text-xs font-medium text-white disabled:opacity-60">
          {busy === 'csv' && <Loader2 size={12} className="animate-spin" />} Download CSV
        </button>
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-2">
        <select className={field} value={filters.status} onChange={set('status')} aria-label="Status">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className={field} value={filters.artist} onChange={set('artist')} aria-label="Artist">
          <option value="">All artists</option>
          {(data?.artists || []).map((a) => <option key={a.artist_user_id} value={a.artist_user_id}>{a.artist_display_name}</option>)}
        </select>
        <input type="date" className={field} value={filters.date_from} onChange={set('date_from')} aria-label="From" />
        <span className="text-xs text-slate-500">to</span>
        <input type="date" className={field} value={filters.date_to} onChange={set('date_to')} aria-label="To" />
        <label className="flex items-center gap-1.5 text-xs text-slate-400">
          <input type="checkbox" checked={filters.include_test} onChange={set('include_test')} className="accent-[#B44FD4]" /> Include test orders
        </label>
      </div>

      {reissued && (
        <div className="mb-3 rounded-xl border border-cyan/30 bg-cyan/[0.06] px-4 py-2.5 text-xs text-sky-100">
          New link for {reissued.license_id} (old link no longer works; email {reissued.email}):{' '}
          <span className="break-all text-cyan">{reissued.url}</span>{' '}
          <button type="button" className={pill} onClick={() => copy(reissued.url)}>Copy</button>
        </div>
      )}

      {!data ? <p className="text-sm text-slate-500">Loading…</p> : (
        <>
          <p className="mb-2 text-xs text-slate-500">
            {data.orders.length} order{data.orders.length === 1 ? '' : 's'}{filters.include_test ? '' : ' (test orders hidden)'}
            {data.truncated && ' · showing the newest 500, narrow the dates to see more'}
          </p>
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500">
                <tr className="border-b border-white/10">
                  {['Date', 'License', 'Track / artist', 'Buyer', 'Tier', 'Paid', 'Status', ''].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.orders.length === 0 && (
                  <tr><td colSpan={8} className="px-3 py-4 text-slate-500">No orders match these filters.</td></tr>
                )}
                {data.orders.map((o) => (
                  <tr key={o.order_id} className="border-b border-white/5 align-top">
                    <td className="whitespace-nowrap px-3 py-2.5 text-slate-300">{day(o.created_at)}</td>
                    <td className="px-3 py-2.5 text-white">
                      {o.license_id}
                      {o.test_mode && <span className="ml-1.5 rounded-full bg-amber-400/10 px-2 py-0.5 text-[11px] text-amber-200">test</span>}
                    </td>
                    <td className="px-3 py-2.5 text-white">{o.track_title}<div className="text-slate-500">{o.artist_display_name}</div></td>
                    <td className="px-3 py-2.5 text-slate-300">{o.buyer_name}{o.buyer_company && ` · ${o.buyer_company}`}<div className="text-slate-500">{o.buyer_email}</div></td>
                    <td className="px-3 py-2.5 text-slate-300">{TIERS[o.tier] || o.tier}{o.include_stems && ' + stems'}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-slate-300">
                      {money(o.amount_total_cents ?? o.price_cents)}
                      {o.tax_cents != null && <div className="text-slate-500">tax {money(o.tax_cents)}</div>}
                      {o.amount_mismatch && <div className="text-red-300">amount mismatch</div>}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-[11px] ${BADGE[o.status] || BADGE.pending}`}>{o.status}</span>
                      {o.email_status && (
                        <div className={o.email_status === 'failed' ? 'mt-1 text-red-300' : 'mt-1 text-slate-500'} title={o.email_error || ''}>
                          email {o.email_status}
                        </div>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right">
                      {o.status === 'fulfilled' && (
                        <>
                          <button type="button" className={pill} disabled={busy === o.order_id} onClick={() => resend(o)}>Resend email</button>
                          <button type="button" className={`${pill} ml-1.5`} disabled={busy === o.order_id} onClick={() => reissue(o)}>Reissue link</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
};

export default AdminOrdersSection;
