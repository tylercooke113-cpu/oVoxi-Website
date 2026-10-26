import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { api, errorMessage } from './api';
import AdminOrdersSection from './AdminOrdersSection';
import Modal from './Modal';

// Admin: hide profiles, delist tracks (PRD-03 9), record exclusive licenses (Brief 25b D5),
// review AI-generated parts (D1) and loop licenses (F). Every action is logged server-side.

const USE_LABEL = { sync: 'Sync', ai: 'AI training' };
const FIELD = 'w-full rounded-md border border-white/10 bg-ink px-2.5 py-1.5 text-sm text-white placeholder:text-slate-600';
const toCents = (v) => {
  const n = parseFloat(String(v).replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) && n > 0 ? Math.round(n * 100) : null;
};
const money = (c) => (c ? `$${(c / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '');

const statusForUse = (s, use) => {
  const sold = (s.exclusive_sold || []).includes(use);
  if (sold) return 'Sold exclusively';
  const status = use === 'sync' ? s.sync_status : s.ai_status;
  if (s.sync_delisted_by_admin) return 'Delisted by admin';
  if (status === 'cleared' && s.on_sync_profile) return 'Live';
  return status || 'Processing';
};

const EMPTY_SALE = { uses: [], buyer_name: '', buyer_company: '', buyer_email: '', sync: '', ai: '',
  term: 'Perpetual', territory: 'Worldwide', quote_id: '' };

// Brief 25b D5: record one exclusive license (total = sync price + AI price).
const ExclusiveForm = ({ track, getToken, onDone, onClose }) => {
  const [f, setF] = useState(EMPTY_SALE);
  const [busy, setBusy] = useState(false);
  const opted = ['sync', 'ai'].filter((u) => (u === 'sync' ? track.consent?.sync : track.consent?.ai_training)
    && !(track.exclusive_sold || []).includes(u));
  const set = (patch) => setF((x) => ({ ...x, ...patch }));
  const total = (f.uses.includes('sync') ? toCents(f.sync) || 0 : 0) + (f.uses.includes('ai') ? toCents(f.ai) || 0 : 0);
  const ok = f.uses.length && f.buyer_name.trim() && /\S+@\S+\.\S+/.test(f.buyer_email)
    && f.uses.every((u) => toCents(f[u]));
  const save = async () => {
    const uses = ['sync', 'ai'].filter((u) => f.uses.includes(u));
    if (!window.confirm(`Record an exclusive license for ${uses.map((u) => USE_LABEL[u]).join(' and ')} on "${track.track_name}" for ${money(total)}? The song comes down for those uses at once and the artist is emailed.`)) return;
    setBusy(true);
    try {
      await api.adminRecordExclusive(getToken, track.id, {
        uses, buyer_name: f.buyer_name.trim(), buyer_company: f.buyer_company.trim(), buyer_email: f.buyer_email.trim(),
        price_cents_sync: uses.includes('sync') ? toCents(f.sync) : null,
        price_cents_ai: uses.includes('ai') ? toCents(f.ai) : null,
        term: f.term.trim() || 'Perpetual', territory: f.territory.trim() || 'Worldwide',
        quote_id: f.quote_id.trim() || null,
      });
      toast.success('Exclusive license recorded.');
      onDone();
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  };
  return (
    <Modal open onClose={() => !busy && onClose()} title={`Record exclusive license: ${track.track_name}`}>
      <div className="space-y-3 text-sm text-slate-300" data-testid="admin-exclusive-form">
        <div className="flex gap-4">
          {opted.map((u) => (
            <label key={u} className="flex items-center gap-2">
              <input type="checkbox" checked={f.uses.includes(u)}
                onChange={(e) => set({ uses: e.target.checked ? [...f.uses, u] : f.uses.filter((x) => x !== u) })} />
              {USE_LABEL[u]}
            </label>
          ))}
          {!opted.length && <span className="text-slate-500">Nothing left to license exclusively.</span>}
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <input className={FIELD} placeholder="Buyer name *" value={f.buyer_name} onChange={(e) => set({ buyer_name: e.target.value })} />
          <input className={FIELD} placeholder="Company" value={f.buyer_company} onChange={(e) => set({ buyer_company: e.target.value })} />
          <input className={FIELD} placeholder="Buyer email *" value={f.buyer_email} onChange={(e) => set({ buyer_email: e.target.value })} />
          <input className={FIELD} placeholder="Quote ID (optional)" value={f.quote_id} onChange={(e) => set({ quote_id: e.target.value })} />
          {f.uses.includes('sync') && <input className={FIELD} placeholder="Price for sync, USD *" inputMode="decimal" value={f.sync} onChange={(e) => set({ sync: e.target.value })} />}
          {f.uses.includes('ai') && <input className={FIELD} placeholder="Price for AI training, USD *" inputMode="decimal" value={f.ai} onChange={(e) => set({ ai: e.target.value })} />}
          <input className={FIELD} placeholder="Term" value={f.term} onChange={(e) => set({ term: e.target.value })} />
          <input className={FIELD} placeholder="Territory" value={f.territory} onChange={(e) => set({ territory: e.target.value })} />
        </div>
        <p className="text-slate-400">Total: <b className="text-white">{money(total) || '$0.00'}</b></p>
        <div className="flex gap-2">
          <button type="button" onClick={save} disabled={busy || !ok}
            className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {busy ? 'Saving…' : 'Record license'}
          </button>
          <button type="button" onClick={onClose} disabled={busy} className="rounded-full border border-white/10 px-5 py-2 text-sm text-slate-300">Cancel</button>
        </div>
      </div>
    </Modal>
  );
};

// Brief 25b D1 and F: the two admin reviews, shown under the track's row.
const Reviews = ({ s, getToken, onChanged }) => {
  const [busy, setBusy] = useState(false);
  const intake = s.intake || {};
  const loops = intake.loops || [];
  const aiPending = intake.ai_tools === 'partial';
  if (!aiPending && !loops.length) return null;
  const act = async (fn, msg) => {
    setBusy(true);
    try { await fn(); toast.success(msg); onChanged(); } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  };
  const openLicense = async (i) => {
    try { const { url } = await api.adminLoopLicense(getToken, s.id, i); window.open(url, '_blank', 'noopener'); }
    catch (err) { toast.error(errorMessage(err)); }
  };
  const btn = 'rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 hover:text-white disabled:opacity-50';
  return (
    <div className="space-y-2 px-4 pb-3 text-xs text-slate-400" data-testid={`admin-reviews-${s.id}`}>
      {aiPending && (
        <div className="flex flex-wrap items-center gap-2">
          <span>AI-generated parts: <b className="text-white">{intake.ai_tools_detail || '(no detail)'}</b></span>
          <span>Review: {s.ai_tools_reviewed?.result || 'pending'}</span>
          <button type="button" className={btn} disabled={busy}
            onClick={() => act(() => api.adminAiToolsReview(getToken, s.id, 'approved'), 'AI parts approved.')}>Approve</button>
          <button type="button" className={btn} disabled={busy}
            onClick={() => window.confirm('Reject? The song comes off the catalog.') && act(() => api.adminAiToolsReview(getToken, s.id, 'rejected'), 'Rejected.')}>Reject</button>
        </div>
      )}
      {loops.length > 0 && (
        <div className="space-y-1">
          {loops.map((lp, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <span>Loop {i + 1}: <b className="text-white">{lp.loop_name}</b> by {lp.creator_name} ({lp.creator_email}, {lp.source})</span>
              {lp.license_key
                ? <button type="button" className={btn} onClick={() => openLicense(i)}>View license</button>
                : <span className="text-amber-400">No license yet</span>}
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-2">
            <span>Loop licenses: {s.loop_licenses_reviewed?.result || 'pending'}</span>
            <button type="button" className={btn} disabled={busy || loops.some((lp) => !lp.license_key)}
              onClick={() => act(() => api.adminLoopReview(getToken, s.id, 'approved'), 'Loop licenses approved.')}>Approve all</button>
            <button type="button" className={btn} disabled={busy}
              onClick={() => window.confirm('Reject the loop licenses? The song stays off sync.') && act(() => api.adminLoopReview(getToken, s.id, 'rejected'), 'Rejected.')}>Reject</button>
          </div>
        </div>
      )}
    </div>
  );
};

const Toggle = ({ on, onClick, busy, label }) => (
  <button type="button" onClick={onClick} disabled={busy}
    className={`rounded-full border px-3 py-1 text-xs transition-colors disabled:opacity-50 ${
      on ? 'border-red-400/40 text-red-300 hover:bg-red-400/10' : 'border-white/10 text-slate-300 hover:text-white'}`}>
    {label}
  </button>
);

const AdminSyncSection = ({ getToken, submissions, onChanged }) => {
  const [profiles, setProfiles] = useState(null);
  const [busy, setBusy] = useState(null);
  const [selling, setSelling] = useState(null);       // track for the exclusive form
  const [sales, setSales] = useState(null);

  const loadSales = useCallback(async () => {
    try { setSales(await api.adminExclusiveLicenses(getToken)); } catch (err) { setSales([]); }
  }, [getToken]);
  useEffect(() => { loadSales(); }, [loadSales]);

  const loadProfiles = useCallback(async () => {
    try { setProfiles(await api.adminProfiles(getToken)); } catch (err) { toast.error(errorMessage(err)); }
  }, [getToken]);

  useEffect(() => { loadProfiles(); }, [loadProfiles]);

  const catalogTracks = (submissions || []).filter((s) => s.consent && (s.consent.sync || s.consent.ai_training));

  const delist = async (s) => {
    const next = !s.sync_delisted_by_admin;
    if (next && !window.confirm(`Delist "${s.track_name}"? It comes off all public pages now.`)) return;
    setBusy(s.id);
    try { await api.adminDelist(getToken, s.id, next); toast.success(next ? 'Delisted.' : 'Relisted if it still clears.'); onChanged(); }
    catch (err) { toast.error(errorMessage(err)); } finally { setBusy(null); }
  };

  const hide = async (p) => {
    setBusy(p.slug);
    try { await api.adminHide(getToken, p.slug, !p.hidden_by_admin); await loadProfiles(); }
    catch (err) { toast.error(errorMessage(err)); } finally { setBusy(null); }
  };

  return (
    <div className="flex flex-col gap-8" data-testid="admin-sync">
      <AdminOrdersSection getToken={getToken} />
      <section>
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Sync profiles</h3>
        {!profiles ? <p className="text-sm text-slate-500">Loading…</p> : profiles.length === 0 ? (
          <p className="text-sm text-slate-500">No profiles yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-sm">
              <tbody>
                {profiles.map((p) => (
                  <tr key={p.slug} className="border-b border-white/5">
                    <td className="px-4 py-3 text-white">{p.display_name}</td>
                    <td className="px-4 py-3"><a href={`/artist/${p.slug}`} target="_blank" rel="noopener noreferrer" className="text-cyan">/artist/{p.slug}</a></td>
                    <td className="px-4 py-3 text-right">
                      <Toggle on={p.hidden_by_admin} busy={busy === p.slug} onClick={() => hide(p)}
                        label={p.hidden_by_admin ? 'Unhide photo and bio' : 'Hide photo and bio'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Catalog tracks</h3>
        {catalogTracks.length === 0 ? <p className="text-sm text-slate-500">No catalog tracks yet.</p> : (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-sm">
              <tbody>
                {catalogTracks.map((s) => {
                  const uses = [s.consent.sync && 'sync', s.consent.ai_training && 'ai'].filter(Boolean);
                  const canSell = s.exclusive && uses.some((u) => !(s.exclusive_sold || []).includes(u));
                  return (
                    <React.Fragment key={s.id}>
                      <tr className="border-b border-white/5" data-testid={`admin-track-${s.id}`}>
                        <td className="px-4 py-3 text-white">
                          {s.track_name}
                          {s.exclusive && <span className="ml-2 rounded-full border border-cyan/40 px-2 py-0.5 text-[10px] text-cyan">Exclusive</span>}
                        </td>
                        <td className="px-4 py-3 text-slate-400">{s.artist_name}</td>
                        <td className="px-4 py-3 text-slate-400">
                          {uses.map((u) => <div key={u}>{USE_LABEL[u]}: {statusForUse(s, u)}</div>)}
                        </td>
                        <td className="px-4 py-3"><a href={`/catalog/track/${s.id}`} target="_blank" rel="noopener noreferrer" className="text-cyan">View</a></td>
                        <td className="space-x-2 whitespace-nowrap px-4 py-3 text-right">
                          {canSell && (
                            <Toggle on={false} busy={false} onClick={() => setSelling(s)} label="Record exclusive license" />
                          )}
                          <Toggle on={!!s.sync_delisted_by_admin} busy={busy === s.id} onClick={() => delist(s)}
                            label={s.sync_delisted_by_admin ? 'Relist' : 'Delist'} />
                        </td>
                      </tr>
                      <tr><td colSpan={5}><Reviews s={s} getToken={getToken} onChanged={onChanged} /></td></tr>
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Exclusive licenses</h3>
        {!sales ? <p className="text-sm text-slate-500">Loading…</p> : sales.length === 0 ? (
          <p className="text-sm text-slate-500">None yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-sm">
              <tbody>
                {sales.map((l) => {
                  const t = (submissions || []).find((x) => x.id === l.track_id);
                  return (
                    <tr key={l.id} className="border-b border-white/5">
                      <td className="px-4 py-3 text-white">{t?.track_name || l.track_id}</td>
                      <td className="px-4 py-3 text-slate-400">{l.uses.map((u) => USE_LABEL[u]).join(' + ')}</td>
                      <td className="px-4 py-3 text-slate-400">{l.buyer_name}{l.buyer_company ? `, ${l.buyer_company}` : ''}</td>
                      <td className="px-4 py-3 text-slate-400">{money(l.total_cents)}</td>
                      <td className="px-4 py-3 text-slate-400">{l.term}, {l.territory}</td>
                      <td className="px-4 py-3 text-slate-500">{new Date(l.granted_at).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selling && (
        <ExclusiveForm track={selling} getToken={getToken} onClose={() => setSelling(null)}
          onDone={() => { setSelling(null); onChanged(); loadSales(); }} />
      )}
    </div>
  );
};

export default AdminSyncSection;
