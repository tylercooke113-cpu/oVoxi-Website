import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { verifyApi } from '../sync/api';

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : '');

const VIEW = {
  active: { icon: '✓', cls: 'text-green-400 bg-green-400/15', title: 'Valid license', body: () => 'This license is active.' },
  expired: { icon: '✕', cls: 'text-red-400 bg-red-400/12', title: 'License expired', body: (l) => `The term of this license ended on ${fmt(l.term_end)}.` },
  refunded: { icon: '✕', cls: 'text-red-400 bg-red-400/12', title: 'No longer valid', body: (l) => `This license was refunded on ${fmt(l.refunded_at)} and does not cover any use.` },
  test: { icon: '✕', cls: 'text-slate-400 bg-slate-400/12', title: 'Test license', body: () => 'This is a test license and does not cover any use.' },
};

export default function VerifyPage() {
  const { licenseId } = useParams();
  const navigate = useNavigate();
  const [state, setState] = useState({ phase: licenseId ? 'loading' : 'idle', lic: null });
  const [input, setInput] = useState('');

  useEffect(() => {
    if (!licenseId) { setState({ phase: 'idle', lic: null }); return undefined; }
    let alive = true;
    setState({ phase: 'loading', lic: null });
    verifyApi.get(licenseId)
      .then((lic) => { if (alive) setState({ phase: 'found', lic }); })
      .catch((e) => { if (alive) setState({ phase: e?.response?.status === 404 ? 'notfound' : 'error', lic: null }); });
    return () => { alive = false; };
  }, [licenseId]);

  const submit = (e) => { e.preventDefault(); const v = input.trim().toUpperCase(); if (v) navigate(`/verify/${encodeURIComponent(v)}`); };

  let card = null;
  if (state.phase === 'loading') {
    card = <div className="p-8 text-center"><Loader2 className="mx-auto animate-spin text-electric" size={28} /></div>;
  } else if (state.phase === 'notfound' || state.phase === 'error') {
    card = (
      <div className="flex items-center gap-4 p-6">
        <div className="flex h-13 w-13 items-center justify-center rounded-full bg-slate-400/12 text-2xl text-slate-400">?</div>
        <div>
          <h2 className="font-heading text-xl font-extrabold text-white">No license found</h2>
          <p className="mt-1 text-sm text-slate-400">Check the License ID and try again. IDs look like OVX- followed by 10 letters and numbers.</p>
        </div>
      </div>
    );
  } else if (state.phase === 'found') {
    const l = state.lic;
    const v = VIEW[l.status] || VIEW.active;
    const full = l.status === 'active' || l.status === 'expired';
    const rows = full
      ? [['License ID', l.license_id], ['Track', `${l.track_title} by ${l.artist_display_name}`], ['License type', l.license_label],
         ['Licensed to', l.licensed_to], ['Project', l.project_name], ['Territory', l.territory], ['Term', l.term_label],
         ['Issued', fmt(l.issued_at)], ['Terms version', l.terms_version]]
      : [['License ID', l.license_id], ['Track', `${l.track_title} by ${l.artist_display_name}`], ['License type', l.license_label], ['Issued', fmt(l.issued_at)]];
    card = (
      <>
        <div className="flex items-center gap-4 p-6">
          <div className={`flex h-13 w-13 items-center justify-center rounded-full text-2xl ${v.cls}`}>{v.icon}</div>
          <div>
            <h2 className="font-heading text-xl font-extrabold text-white">{v.title}</h2>
            <p className="mt-1 text-sm text-slate-400">{v.body(l)}</p>
          </div>
        </div>
        <div className="border-t border-white/10">
          {rows.filter(([, val]) => val).map(([k, val]) => (
            <div key={k} className="flex justify-between gap-4 border-b border-white/10 px-6 py-3 text-sm">
              <span className="text-slate-500">{k}</span><span className="text-right">{val}</span>
            </div>
          ))}
        </div>
        <div className="px-6 py-4 text-xs text-slate-500">Verified by oVoxi at ovoxi.net/verify</div>
      </>
    );
  }

  return (
    <div className="mx-auto max-w-xl px-4 pb-20 pt-28">
      <div className="mb-6 text-center">
        <h1 className="font-heading text-2xl font-semibold text-white">License verification</h1>
        <p className="mt-1 text-sm text-slate-400">Check that an oVoxi music license is real and active.</p>
      </div>
      {card && <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02]">{card}</div>}
      <form onSubmit={submit} className="mt-5 flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Enter a License ID, e.g. OVX-7K2M9QX4TB"
          className="flex-1 rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white focus:border-electric focus:outline-none" />
        <button type="submit" className="rounded-full bg-gradient-brand px-5 py-2.5 text-sm font-semibold text-white">Check</button>
      </form>
      <p className="mt-3.5 text-center text-xs text-slate-500">This page shows license details only. It never shows payment details or email addresses.</p>
    </div>
  );
}
