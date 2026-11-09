import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../sync/api';
import { uploadersApi, uploaderApi, STATUS, USE_SHORT, shortDate } from './api';

// Brief 28 D6: admin view of every Upload Authorization, plus "Act for an artist" for artists
// who added OVOXI. Acting reuses the Vault and Upload pages (?for=), which record the admin.

const PILL = { ok: 'border-green-400/35 text-green-400', warn: 'border-amber-400/35 text-amber-400', off: 'border-white/10 text-slate-500' };
const Pill = ({ cls, children }) => (
  <span className={`mr-1 inline-block whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] ${cls}`}>{children}</span>
);

export default function AdminUploadersSection({ getToken }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState('');
  const [statusF, setStatusF] = useState('');
  const [kindF, setKindF] = useState('');
  const [search, setSearch] = useState('');
  const [ovoxi, setOvoxi] = useState(null);
  const [actFor, setActFor] = useState('');

  useEffect(() => {
    let live = true;
    uploadersApi.adminList(getToken, statusF ? { status: statusF } : {})
      .then((r) => { if (live) { setRows(r); setErr(''); } })
      .catch((e) => { if (live) { setRows([]); setErr(errorMessage(e, 'Could not load authorizations.')); } });
    return () => { live = false; };
  }, [getToken, statusF]);

  useEffect(() => {
    let live = true;
    uploaderApi.artists(getToken)
      .then((l) => { if (live) setOvoxi(l.filter((a) => a.is_ovoxi)); })
      .catch(() => { if (live) setOvoxi([]); });
    return () => { live = false; };
  }, [getToken]);

  const q = search.trim().toLowerCase();
  const shown = (rows || []).filter((r) => (!kindF || r.kind === kindF)
    && (!q || [r.artist_name, r.uploader_name, r.uploader_email].some((v) => (v || '').toLowerCase().includes(q))));
  const picked = (ovoxi || []).find((a) => a.artist_user_id === actFor);
  const sel = 'rounded-lg border border-white/10 bg-black px-3 py-2 text-sm text-white';

  return (
    <div className="flex flex-col gap-8" data-testid="admin-uploaders">
      <section data-testid="admin-act-for">
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Act for an artist</h3>
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
          {ovoxi === null ? <p className="text-sm text-slate-500">Loading...</p> : ovoxi.length === 0 ? (
            <p className="text-sm text-slate-500">No artist has added OVOXI as an uploader yet.</p>
          ) : (
            <>
              <select value={actFor} onChange={(e) => setActFor(e.target.value)} className={`${sel} w-full sm:w-auto`} aria-label="Acting for">
                <option value="">Choose an artist</option>
                {ovoxi.map((a) => (
                  <option key={a.artist_user_id} value={a.artist_user_id}>
                    {a.artist_name} ({a.uses.map((u) => USE_SHORT[u] || u).join(', ')})
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-slate-500">
                Only artists who signed an Upload Authorization naming OVOXI are listed. Every upload and edit records you as the admin who took it.
              </p>
              {picked && (
                <div className="mt-4 rounded-xl border border-[#4FC3F7]/30 bg-[#4FC3F7]/[0.06] p-3.5 text-sm text-sky-100" data-testid="admin-act-for-summary">
                  You will act for <b>{picked.artist_name}</b>. You can upload songs and set {picked.uses.map((u) => USE_SHORT[u] || u).join(' and ')}.
                  You can't turn on Exclusive or see their Wallet, profile or agreements.
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link to={`/vault?for=${encodeURIComponent(picked.artist_user_id)}`}
                      className="rounded-full border border-white/20 px-4 py-1.5 text-sm text-white hover:bg-white/10">Open {picked.artist_name}'s Vault</Link>
                    <Link to={`/upload?for=${encodeURIComponent(picked.artist_user_id)}`}
                      className="rounded-full bg-gradient-brand px-4 py-1.5 text-sm font-semibold text-white">Upload for {picked.artist_name}</Link>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      <section data-testid="admin-authorizations">
        <h3 className="mb-3 font-heading text-lg font-semibold text-white">Upload Authorizations</h3>
        <div className="mb-3 flex flex-wrap gap-2">
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search artist or uploader"
            className={`${sel} min-w-[220px]`} aria-label="Search" />
          <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className={sel} aria-label="Status">
            <option value="">All statuses</option>
            {Object.entries(STATUS).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <select value={kindF} onChange={(e) => setKindF(e.target.value)} className={sel} aria-label="Uploader type">
            <option value="">All uploaders</option>
            <option value="ovoxi">OVOXI only</option>
            <option value="person">People only</option>
          </select>
        </div>
        {err && <p className="mb-3 text-sm text-red-400" role="alert">{err}</p>}
        {rows === null ? <p className="text-sm text-slate-500">Loading...</p> : shown.length === 0 ? (
          <p className="text-sm text-slate-500">None.</p>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                  {['Artist', 'Uploader', 'Uses', 'Status', 'Created'].map((h) => <th key={h} className="px-4 py-2 font-medium">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => {
                  const [label, tone] = STATUS[r.status] || ['Ended', 'off'];
                  return (
                    <tr key={r.id} className="border-b border-white/5" data-testid={`admin-auth-${r.id}`}>
                      <td className="px-4 py-3 text-white">{r.artist_name}</td>
                      <td className="px-4 py-3 text-slate-300">
                        {r.kind === 'ovoxi' ? 'OVOXI, Inc.' : r.uploader_name}
                        <div className="text-xs text-slate-500">{r.kind === 'ovoxi' ? 'OVOXI' : `${r.uploader_role || ''} · ${r.uploader_email || ''}`}</div>
                      </td>
                      <td className="px-4 py-3">{(r.uses || []).map((u) => <Pill key={u} cls="border-white/15 text-slate-300">{USE_SHORT[u] || u}</Pill>)}</td>
                      <td className="px-4 py-3"><Pill cls={PILL[tone]}>{label}</Pill></td>
                      <td className="whitespace-nowrap px-4 py-3 text-slate-400">{shortDate(r.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
