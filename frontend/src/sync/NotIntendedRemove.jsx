import React, { useState } from 'react';
import { toast } from 'sonner';
import { api, errorMessage } from './api';

// Brief 28 D5 / Agreement 12.4 last sentence: on a song an Authorized Uploader added, the
// artist (never the uploader) can remove it as not intended for 30 days after upload.
// Immediate, does not count toward the 12.4 limit, and licenses already sold stay.

const fmt = (iso) => {
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return ''; }
};

export default function NotIntendedRemove({ track, getToken, onUpdated }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const by = track.uploaded_by?.name || 'An Authorized Uploader';

  if (track.not_intended_at) {
    return (
      <p className="mt-4 border-t border-white/10 pt-3 text-sm text-slate-400" data-testid={`vault-not-intended-done-${track.id}`}>
        You removed this on {fmt(track.not_intended_at)}. To license it again, turn its uses back on.
      </p>
    );
  }
  const until = track.not_intended_until ? new Date(track.not_intended_until) : null;
  if (!track.uploaded_by || !until || until.getTime() <= Date.now()) return null;

  const remove = async () => {
    setBusy(true);
    try {
      const updated = await api.notIntended(getToken, track.id);
      onUpdated({ ...track, ...updated });
      toast.success('Removed. No new licenses will be sold for it.');
      setOpen(false);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally { setBusy(false); }
  };

  return (
    <>
      <p className="mt-4 border-t border-white/10 pt-3 text-sm text-slate-400" data-testid={`vault-not-intended-${track.id}`}>
        Didn't mean for this to be uploaded?{' '}
        <button type="button" onClick={() => setOpen(true)} className="text-[#4FC3F7] hover:underline">Remove</button>
        <span className="ml-2 text-xs text-slate-500">Available until {fmt(track.not_intended_until)}.</span>
      </p>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" role="dialog" aria-modal="true"
          aria-labelledby={`ni-title-${track.id}`}>
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0A0A0C] p-6">
            <h4 id={`ni-title-${track.id}`} className="mb-2 font-heading text-lg text-white">Remove "{track.track_name}"?</h4>
            <p className="mb-3 text-sm text-slate-400">
              {by} uploaded this on {fmt(track.upload_date)}. If you didn't mean for it to be licensed, removing it turns off
              every use right away. No new licenses will be sold for it.
            </p>
            <div className="rounded-xl border border-electric/30 bg-electric/[0.06] p-3 text-[13.5px] text-purple-100">
              Licenses already sold for this song stay in place, as your Agreement says. This removal doesn't count toward
              your withdrawal limit.
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} disabled={busy}
                className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 hover:text-white disabled:opacity-40">Keep it</button>
              <button type="button" onClick={remove} disabled={busy} data-testid={`vault-not-intended-confirm-${track.id}`}
                className="rounded-full bg-red-400 px-5 py-2 text-sm font-semibold text-[#0A0A0C] disabled:opacity-40">Remove</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
