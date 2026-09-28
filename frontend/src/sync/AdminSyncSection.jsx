import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { api, errorMessage } from './api';

// Admin: hide profiles, delist tracks (PRD-03 9). Every action is logged server-side.

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

  const loadProfiles = useCallback(async () => {
    try { setProfiles(await api.adminProfiles(getToken)); } catch (err) { toast.error(errorMessage(err)); }
  }, [getToken]);

  useEffect(() => { loadProfiles(); }, [loadProfiles]);

  const syncTracks = (submissions || []).filter((s) => s.consent && s.consent.sync);

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
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Sync tracks</h3>
        {syncTracks.length === 0 ? <p className="text-sm text-slate-500">No sync tracks yet.</p> : (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-sm">
              <tbody>
                {syncTracks.map((s) => (
                  <tr key={s.id} className="border-b border-white/5">
                    <td className="px-4 py-3 text-white">{s.track_name}</td>
                    <td className="px-4 py-3 text-slate-400">{s.artist_name}</td>
                    <td className="px-4 py-3 text-slate-400">
                      {s.sync_delisted_by_admin ? 'Delisted by admin' : s.on_sync_profile ? 'Live' : (s.sync_status || 'Processing')}
                    </td>
                    <td className="px-4 py-3"><a href={`/sync/track/${s.id}`} target="_blank" rel="noopener noreferrer" className="text-cyan">View</a></td>
                    <td className="px-4 py-3 text-right">
                      <Toggle on={!!s.sync_delisted_by_admin} busy={busy === s.id} onClick={() => delist(s)}
                        label={s.sync_delisted_by_admin ? 'Relist' : 'Delist'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};

export default AdminSyncSection;
