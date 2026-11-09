import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import Modal from './Modal';
import { api, errorMessage } from './api';

// Brief 28 C6/D6: admin takedown under Agreement 2.3(f). A real Removal for each chosen use:
// it records the withdrawal, turns the use off and takes effect now for new licenses. It does
// not count toward 12.4. Only the artist can turn a taken-down use back on (in their Vault).

export const TAKEDOWN_REASONS = [
  ['artist_request', 'Artist asked'],
  ['upload_error', 'Upload error'],
  ['rights_problem', 'Rights problem'],
];
const USES = [['sync', 'Sync placements'], ['ai_training', 'AI training']];

export default function TakedownDialog({ track, getToken, onClose, onDone }) {
  const live = USES.filter(([u]) => track?.consent?.[u]);
  const [uses, setUses] = useState([]);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (track) { setUses(live.map(([u]) => u)); setReason(''); setNote(''); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [track?.id]);

  const toggle = (u) => setUses((x) => (x.includes(u) ? x.filter((y) => y !== u) : [...x, u]));
  const canSubmit = uses.length > 0 && !!reason && !busy;

  const submit = async () => {
    setBusy(true);
    try {
      await api.adminTakedown(getToken, track.id, { uses, reason, note: note.trim() || null });
      toast.success(uses.length === 1 ? 'Use taken down.' : 'Uses taken down.');
      onDone();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally { setBusy(false); }
  };

  return (
    <Modal open={!!track} onClose={() => !busy && onClose()} title={track ? `Take down "${track.track_name}"` : ''}>
      {track && (
        <div data-testid="takedown-dialog">
          <p className="mb-4 text-sm text-slate-400">
            {track.artist_name}. Takes effect right away for new licenses. Licenses already sold stay in place.
            Does not count toward the artist's withdrawal limit.
          </p>
          <div className="mb-1.5 text-[13.5px] font-medium text-slate-300">Uses to take down</div>
          {live.length === 0 && <p className="text-sm text-slate-500">No use is on for this song.</p>}
          {live.map(([u, label]) => (
            <label key={u} className="flex items-center gap-2 py-1 text-sm text-slate-300">
              <input type="checkbox" data-use={u} className="accent-[#9B59D4]" checked={uses.includes(u)} onChange={() => toggle(u)} />
              {label}
            </label>
          ))}
          <label className="mb-1.5 mt-4 block text-[13.5px] font-medium text-slate-300" htmlFor="td-reason">Reason</label>
          <select id="td-reason" value={reason} onChange={(e) => setReason(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white">
            <option value="">Choose a reason</option>
            {TAKEDOWN_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <label className="mb-1.5 mt-4 block text-[13.5px] font-medium text-slate-300" htmlFor="td-note">Note (saved to the admin log)</label>
          <textarea id="td-note" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)}
            className="min-h-[80px] w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white" />
          <p className="mt-2 text-xs text-slate-500">
            To restore a use, the artist turns it back on in their Vault. Release hold can't bring it back.
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={onClose} disabled={busy}
              className="rounded-full border border-white/10 px-5 py-2 text-sm text-slate-300 disabled:opacity-40">Cancel</button>
            <button type="button" onClick={submit} disabled={!canSubmit} data-testid="takedown-submit"
              className="rounded-full bg-red-400 px-5 py-2 text-sm font-semibold text-[#0A0A0C] disabled:opacity-40">
              {`Take down ${uses.length} use${uses.length === 1 ? '' : 's'}`}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
