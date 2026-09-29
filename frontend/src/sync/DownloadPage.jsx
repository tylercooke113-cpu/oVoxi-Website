import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Download, Loader2 } from 'lucide-react';
import { errorMessage } from './api';
import { checkoutApi } from './checkout';

// /license/:token (PRD-03 7.3). Each click asks the server for a fresh 5-minute link
// and opens it, which saves the file.

export const TIER_LABELS = { creator: 'Creator', creator_pro: 'Creator Pro', business_social: 'Business Social' };

const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');

const DownloadPage = () => {
  const { token } = useParams();
  const [state, setState] = useState({ loading: true, data: null, error: '' });
  const [busy, setBusy] = useState('');
  const [fileError, setFileError] = useState({});

  useEffect(() => {
    let alive = true;
    checkoutApi.downloads(token)
      .then((data) => alive && setState({ loading: false, data, error: '' }))
      .catch((err) => alive && setState({ loading: false, data: null, error: errorMessage(err, 'This download link is invalid or has expired.') }));
    return () => { alive = false; };
  }, [token]);

  const download = async (name) => {
    setBusy(name);
    setFileError({});
    try {
      const { url } = await checkoutApi.downloadFile(token, name);
      setState((s) => ({ ...s, data: { ...s.data, files: s.data.files.map((f) => (f.name === name ? { ...f, remaining: Math.max(0, f.remaining - 1) } : f)) } }));
      window.location.assign(url);
    } catch (err) {
      setFileError({ [name]: errorMessage(err, 'Download unavailable. Try again.') });
    } finally {
      setBusy('');
    }
  };

  if (state.loading) return <div className="flex min-h-[60vh] justify-center bg-ink pt-40"><Loader2 className="animate-spin text-electric" size={32} /></div>;
  if (state.error) {
    return (
      <div className="flex min-h-screen items-start justify-center bg-ink px-4 pt-32" data-testid="download-error">
        <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.015] p-7 text-center">
          <h1 className="font-heading text-2xl font-extrabold text-white">Link unavailable</h1>
          <p className="mt-2 text-sm text-slate-400">{state.error}</p>
          <p className="mt-2 text-xs text-slate-500">Need a new link? Email tyler@ovoxi.net with your License ID.</p>
        </div>
      </div>
    );
  }

  const d = state.data;
  return (
    <div className="min-h-screen bg-ink px-4 pb-20 pt-28" data-testid="download-page">
      <div className="mx-auto max-w-2xl">
        {d.test_mode && (
          <p className="mb-4 rounded-xl border border-amber-400/30 bg-amber-400/[0.06] px-4 py-2.5 text-[13px] text-amber-100">
            Test order. These files are for testing and the certificate is not a valid license.
          </p>
        )}
        <p className="text-xs uppercase tracking-[0.2em] text-cyan">Your sync license</p>
        <h1 className="mt-1.5 font-heading text-4xl font-extrabold text-white">{d.track_title}</h1>
        <p className="mt-2 text-sm text-slate-400">
          {d.artist_display_name} · {TIER_LABELS[d.tier] || d.tier}{d.include_stems ? ' + stems' : ''} · License {d.license_id}
        </p>
        <p className="mt-1 text-xs text-slate-500">This link works until {fmtDate(d.expires_at)}. Each file can be downloaded up to 10 times.</p>
        <div className="mt-6 space-y-2.5">
          {d.files.map((f) => (
            <div key={f.name} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.015] px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm text-white">{f.label}</p>
                <p className={`text-xs ${fileError[f.name] ? 'text-red-300' : 'text-slate-500'}`}>
                  {fileError[f.name] || `${f.remaining} download${f.remaining === 1 ? '' : 's'} left`}
                </p>
              </div>
              <button type="button" onClick={() => download(f.name)} disabled={busy !== '' || f.remaining === 0}
                data-testid={`download-${f.name}`}
                className="inline-flex flex-none items-center gap-1.5 rounded-full border border-white/15 px-4 py-2 text-xs text-white hover:border-white/30 disabled:opacity-40">
                {busy === f.name ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} Download
              </button>
            </div>
          ))}
        </div>
        <p className="mt-6 text-xs text-slate-500">Questions? Email tyler@ovoxi.net with your License ID.</p>
      </div>
    </div>
  );
};

export default DownloadPage;
