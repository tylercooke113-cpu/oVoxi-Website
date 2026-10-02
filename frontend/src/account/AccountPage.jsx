import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser, useAuth } from '@clerk/clerk-react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { accountApi, errorMessage } from '../sync/api';

const CHIP = {
  active: 'text-green-400 border-green-400/25 bg-green-400/[0.08]',
  expired: 'text-amber-300 border-amber-400/25 bg-amber-400/[0.08]',
  test: 'text-amber-300 border-amber-400/25 bg-amber-400/[0.08]',
  refunded: 'text-red-300 border-red-400/25 bg-red-400/[0.08]',
  void: 'text-red-300 border-red-400/25 bg-red-400/[0.08]',
};
const CHIP_LABEL = { active: 'Active', expired: 'Expired', test: 'Test', refunded: 'Refunded', void: 'Void' };
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '');

const LicenseCard = ({ lic, getToken }) => {
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const dead = lic.status === 'refunded' || lic.status === 'void';
  const go = async (fn) => { try { window.location.assign(await fn()); } catch (e) { toast.error(errorMessage(e)); } };
  const copyVerify = async () => {
    const url = `${window.location.origin}/verify/${lic.license_id}`;
    try { await navigator.clipboard.writeText(url); toast.success('Verification link copied.'); }
    catch { toast.error('Could not copy. The link is: ' + url); }
  };
  const paidMedia = lic.media_spend_cap_cents
    ? `Up to $${(lic.media_spend_cap_cents / 100).toLocaleString()}` : (lic.media_summary || '—');
  return (
    <div className="mt-3 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-heading text-[17px] font-semibold text-white">
            {lic.track_title} <span className="text-sm font-light text-slate-400">· {lic.artist_display_name}</span>
          </h3>
          <div className="mt-0.5 text-[13px] text-slate-400">
            {lic.license_label} · {lic.project_name} · issued {fmtDate(lic.issued_at)}
          </div>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${CHIP[lic.status] || CHIP.active}`}>
          {CHIP_LABEL[lic.status] || lic.status}
        </span>
      </div>
      <div className="mt-3.5 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px] sm:grid-cols-4">
        {[['License ID', lic.license_id], ['Territory', lic.territory], ['Term', lic.term_label], ['Paid media', paidMedia]].map(([k, v]) => (
          <div key={k}><span className="block text-[11px] uppercase tracking-wide text-slate-500">{k}</span>{v}</div>
        ))}
      </div>
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        {dead ? (
          <span className="text-[13px] text-slate-400">This license was refunded and is no longer valid.</span>
        ) : (
          <>
            <button onClick={() => go(() => accountApi.certificate(getToken, lic.license_id))}
              className="rounded-full bg-gradient-brand px-3.5 py-1.5 text-[13px] font-medium text-white">Certificate (PDF)</button>
            <div className="relative">
              <button onClick={() => setMenu((v) => !v)}
                className="rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-slate-300 hover:text-white">Download files</button>
              {menu && (
                <div className="absolute z-10 mt-1 w-56 rounded-xl border border-white/10 bg-black/95 p-1">
                  {(lic.files || []).map((f) => (
                    <button key={f.name} onClick={() => { setMenu(false); go(() => accountApi.file(getToken, lic.license_id, f.name)); }}
                      className="block w-full px-3 py-2 text-left text-[13px] text-slate-300 hover:text-white">{f.label}</button>
                  ))}
                  {!(lic.files || []).length && <p className="px-3 py-2 text-[13px] text-slate-500">No files available.</p>}
                </div>
              )}
            </div>
            <button onClick={copyVerify} className="rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-slate-300 hover:text-white">Copy verification link</button>
          </>
        )}
        <button onClick={() => setOpen((v) => !v)} className="rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-slate-300 hover:text-white">
          {open ? 'Hide details' : 'Details'}
        </button>
      </div>
      {open && (
        <div className="mt-3.5 border-t border-white/10 pt-3 text-[13px] text-slate-300">
          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
            <div><span className="block text-[11px] uppercase tracking-wide text-slate-500">Client</span>{lic.client || '—'}</div>
            <div><span className="block text-[11px] uppercase tracking-wide text-slate-500">Files</span>{(lic.files || []).map((f) => f.label).join(', ') || '—'}</div>
            <div><span className="block text-[11px] uppercase tracking-wide text-slate-500">Terms version</span>{lic.terms_version}</div>
          </div>
          <h4 className="mt-3 mb-1.5 text-[11px] uppercase tracking-wide text-slate-500">Cue sheet information</h4>
          <table className="w-full border-collapse text-[13px]">
            <thead><tr className="text-slate-500">{['Name', 'Role', 'PRO', 'IPI'].map((h) => <th key={h} className="border-b border-white/10 px-2 py-1.5 text-left font-medium">{h}</th>)}</tr></thead>
            <tbody>{(lic.cue_sheet || []).map((c, i) => (
              <tr key={i}>{[c.name, c.role, c.society, c.ipi || 'None'].map((v, j) => <td key={j} className="border-b border-white/10 px-2 py-1.5">{v}</td>)}</tr>
            ))}</tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">File cue sheets with the broadcaster or distributor when your use requires one.</p>
        </div>
      )}
    </div>
  );
};

export default function AccountPage() {
  const navigate = useNavigate();
  const { isLoaded, isSignedIn, user } = useUser();
  const { getToken } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [tab, setTab] = useState('lic');
  const [q, setQ] = useState('');
  const started = useRef(false);

  useEffect(() => {
    if (isLoaded && !isSignedIn) navigate('/login?next=/account', { replace: true });
  }, [isLoaded, isSignedIn, navigate]);

  useEffect(() => {
    if (!isSignedIn || started.current) return;
    started.current = true;
    accountApi.licenses(getToken).then(setData).catch(() => setError(true));
  }, [isSignedIn, getToken]);

  const licenses = useMemo(() => data?.licenses || [], [data]);
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return licenses;
    return licenses.filter((l) => [l.track_title, l.project_name, l.license_id].some((x) => (x || '').toLowerCase().includes(s)));
  }, [licenses, q]);

  if (!isLoaded || (!data && !error)) {
    return <div className="flex min-h-screen items-center justify-center bg-ink"><Loader2 className="animate-spin text-electric" size={32} /></div>;
  }
  const company = licenses.find((l) => l.licensee_company)?.licensee_company;
  const name = `${user?.firstName || ''} ${user?.lastName || ''}`.trim();
  const email = user?.primaryEmailAddress?.emailAddress || '';

  return (
    <div className="min-h-screen bg-ink pt-24 pb-16 px-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="font-heading text-3xl font-semibold text-white">My account</h1>
        <p className="mt-1 text-sm text-slate-400">{[name, company, email].filter(Boolean).join(' · ')}</p>
        <div className="mt-6 flex gap-1 border-b border-white/10">
          {[['lic', 'Licenses'], ['sub', 'Subscription']].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`-mb-px border-b-2 px-4 py-2.5 text-sm ${tab === k ? 'border-electric text-white' : 'border-transparent text-slate-400 hover:text-white'}`}>{l}</button>
          ))}
        </div>
        {tab === 'sub' ? (
          <div className="mt-5 rounded-2xl border border-dashed border-white/10 p-7 text-center text-slate-400">
            <p className="mb-1.5 font-medium text-white">No active subscription</p>
            <p className="mb-4 text-sm">License unlimited projects from the full catalog, from $19 a month.</p>
            <a href="/pricing" className="inline-block rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white">See plans</a>
          </div>
        ) : licenses.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-white/10 p-7 text-center text-slate-400">
            <p className="mb-1.5 font-medium text-white">No licenses yet</p>
            <p className="mb-4 text-sm">Licenses you buy or create with a subscription show up here, with certificates and downloads.</p>
            <a href="/sync" className="inline-block rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white">Browse the sync library</a>
          </div>
        ) : (
          <div className="mt-5">
            <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by track, project or License ID"
              className="w-full max-w-sm rounded-lg border border-white/10 bg-black px-3 py-2 text-sm text-white focus:border-electric focus:outline-none" />
            {filtered.map((l) => <LicenseCard key={l.license_id} lic={l} getToken={getToken} />)}
            {data?.linking === 'unavailable' && (
              <p className="mt-3 text-xs text-slate-500">We couldn't check for past purchases right now. Refresh to try again.</p>
            )}
            <p className="mt-3.5 text-xs text-slate-500">Single-track purchases made before you created your account appear here automatically when they used this account's email address.</p>
          </div>
        )}
      </div>
    </div>
  );
}
