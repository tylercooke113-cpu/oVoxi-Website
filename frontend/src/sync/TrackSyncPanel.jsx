import React, { useCallback, useState } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import Modal from './Modal';
import SyncIntakeFields, { EMPTY_INTAKE, buildIntakePayload, isIntakeValid } from './SyncIntakeFields';
import { api, errorMessage } from './api';
import { reasonText } from './labels';
import { BPM_MAX, BPM_MIN, MAJOR_KEYS, MAX_MOODS, MINOR_KEYS, MOODS } from './constants';

// Per-track "Uses and details" panel in the Vault (PRD-03 4.2, 4.3, 4.4).

const CONFIRM_COPY = {
  'ai_training:grant': ['Use this track for AI training?', 'It will be included in future AI deliveries.'],
  'ai_training:withdraw': ['Stop using this track for AI training?',
    'It will be left out of future AI deliveries. Deliveries already made are not recalled.'],
  'sync:withdraw': ['Remove from the OVOXI Catalog?',
    'It will no longer be listed for sale. Licenses already sold stay valid.'],
  'exclusive_buyout:withdraw': ['Stop allowing exclusive buyouts?',
    'Buyers will no longer be able to buy exclusive rights to this track. Buyouts already granted are not affected.'],
  'ai_exclusive:grant': ['Make AI training exclusive to OVOXI?',
    'You earn 50% instead of 33% on AI training sales of this song, and agree not to license AI training for it anywhere else.'],
};

// The exclusive wind-down ends 30 days after withdrawal (Agreement 12.4).
const fmtEndDate = (iso) => {
  const d = new Date(iso);
  d.setDate(d.getDate() + 30);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const Switch = ({ on, onClick, disabled, label }) => (
  <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={onClick} disabled={disabled}
    className={`relative h-5 w-9 flex-none rounded-full transition-colors disabled:opacity-50 ${on ? 'bg-electric' : 'bg-white/15'}`}>
    <span className={`absolute top-0.5 h-4 w-4 rounded-full transition-all ${on ? 'left-[18px] bg-white' : 'left-0.5 bg-slate-400'}`} />
  </button>
);

const SmallBtn = ({ primary, ...props }) => (
  <button type="button" {...props}
    className={`rounded-md border px-2.5 py-1 text-xs transition-colors disabled:opacity-50 ${
      primary ? 'border-electric bg-electric text-white hover:bg-electric/90'
        : 'border-white/10 text-slate-300 hover:border-electric/40 hover:text-white'}`} />
);

const sourceLabel = (source) => (source === 'artist' ? 'you entered' : source === 'detected' ? 'detected' : '');

const HeldNote = ({ field, meta }) => {
  const value = meta[field];
  const detected = meta[`${field}_detected`];
  const name = field === 'bpm' ? 'BPM' : 'key';
  if (meta[`${field}_source`] === 'detected') {
    return <>You chose "I'm unsure" for the {name}. We detected <b className="text-white">{value}</b>. Please confirm.</>;
  }
  return <>Your {name} ({value}) doesn't match what we detected ({detected ?? 'unknown'}). Please confirm yours or correct it.</>;
};

const ValueEditor = ({ field, initial, busy, onSave, onCancel }) => {
  const [v, setV] = useState(initial != null ? String(initial) : '');
  if (field === 'bpm') {
    const n = parseFloat(v);
    const ok = Number.isFinite(n) && n >= BPM_MIN && n <= BPM_MAX;
    return (
      <div className="flex items-center gap-2">
        <Input inputMode="decimal" value={v} aria-label="BPM"
          onChange={(e) => setV(e.target.value.replace(/[^0-9.]/g, '').slice(0, 5))}
          className="h-8 w-24 border-white/10 bg-ink text-white" />
        <SmallBtn primary disabled={!ok || busy} onClick={() => onSave(Math.round(n * 10) / 10)}>Save</SmallBtn>
        <SmallBtn onClick={onCancel} disabled={busy}>Cancel</SmallBtn>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <Select value={v} onValueChange={setV}>
        <SelectTrigger aria-label="Key" className="h-8 w-36 border-white/10 bg-ink text-white"><SelectValue placeholder="Key" /></SelectTrigger>
        <SelectContent className="max-h-72 border-white/10 bg-ink-2 text-white">
          {[...MAJOR_KEYS, ...MINOR_KEYS].map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}
        </SelectContent>
      </Select>
      <SmallBtn primary disabled={!v || busy} onClick={() => onSave(v)}>Save</SmallBtn>
      <SmallBtn onClick={onCancel} disabled={busy}>Cancel</SmallBtn>
    </div>
  );
};

const COSIGN_STATUS = {
  signed: ['Signed', 'text-green-400'],
  declined: ['Declined', 'text-red-400'],
  pending: ['Waiting', 'text-amber-400'],
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString(); } catch { return ''; }
};

// Brief 22 C6: co-owner signing status in the Vault, with resend and edit-email.
const CosignBlock = ({ track, getToken, onUpdated }) => {
  const [busy, setBusy] = useState(null);     // request_id currently acting
  const [editing, setEditing] = useState(null); // request_id being edited
  const [draft, setDraft] = useState('');
  const rows = track.cosign || [];

  const refresh = (patch) => onUpdated({ ...track, ...patch });

  const resend = async (req) => {
    setBusy(req.request_id);
    try {
      await api.cosignResend(getToken, track.id, req.request_id);
      toast.success('Invite resent.');
      refresh({ cosign: rows.map((x) => (x.request_id === req.request_id
        ? { ...x, sent_at: new Date().toISOString() } : x)) });
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(null); }
  };

  const saveEmail = async (req) => {
    const email = draft.trim();
    setBusy(req.request_id);
    try {
      await api.cosignEditEmail(getToken, track.id, req.request_id, email);
      toast.success('Email updated and invite resent.');
      refresh({ cosign: rows.map((x) => (x.request_id === req.request_id
        ? { ...x, email, sent_at: new Date().toISOString() } : x)) });
      setEditing(null);
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(null); }
  };

  if (!track.cosign_required) return null;

  return (
    <div className="md:col-span-3 border-t border-white/10 pt-4" data-testid={`vault-cosign-${track.id}`}>
      <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">Co-owner signatures</p>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-500">No co-owner invites yet.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((req) => {
            const [label, color] = COSIGN_STATUS[req.status] || COSIGN_STATUS.pending;
            const date = req.signed_at || req.declined_at || req.sent_at;
            const pending = req.status === 'pending';
            const acting = busy === req.request_id;
            return (
              <li key={req.request_id} className="rounded-lg border border-white/10 bg-ink p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-white">{(req.legal_names || []).join(', ') || req.email}</p>
                    <p className="truncate text-xs text-slate-500">{req.email}</p>
                  </div>
                  <span className={`text-xs font-medium ${color}`}>
                    ● {label}{date ? ` · ${fmtDate(date)}` : ''}
                  </span>
                </div>
                {pending && !req.sent_at && (
                  <p className="mt-1 text-xs text-amber-400">Not sent</p>
                )}
                {pending && editing === req.request_id ? (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Input
                      type="email"
                      aria-label="Co-owner email"
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      className="h-8 w-56 border-white/10 bg-ink text-white"
                    />
                    <SmallBtn primary disabled={acting || !draft.trim()} onClick={() => saveEmail(req)}>Save</SmallBtn>
                    <SmallBtn disabled={acting} onClick={() => setEditing(null)}>Cancel</SmallBtn>
                  </div>
                ) : pending && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <SmallBtn disabled={acting} onClick={() => resend(req)}>
                      {acting ? <Loader2 size={12} className="animate-spin" /> : 'Resend'}
                    </SmallBtn>
                    <SmallBtn disabled={acting} onClick={() => { setDraft(req.email || ''); setEditing(req.request_id); }}>
                      Edit email
                    </SmallBtn>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

const SyncStatus = ({ track }) => {
  if (!track.consent.sync) {
    return (
      <>
        <p className="text-sm text-slate-500">Not in the OVOXI Catalog</p>
        <p className="mt-1 text-xs text-slate-500">Turn on Sync placements to add it. You'll answer the sync questions first.</p>
      </>
    );
  }
  if (track.status === 'CONFLICT' || track.sync_status === 'conflict') {
    return <p className="text-sm font-medium text-red-400">● Conflict: this recording appears to match existing copyrighted material</p>;
  }
  if (track.delisted_by_admin) {
    return (
      <>
        <p className="text-sm font-medium text-red-400">● Removed by OVOXI</p>
        <p className="mt-1 text-xs text-slate-500">Contact support if you think this is a mistake.</p>
      </>
    );
  }
  if (track.sync_status === 'cleared' && track.on_sync_profile) {
    const url = `${window.location.origin}/catalog/track/${track.id}`;
    const copy = async () => {
      try { await navigator.clipboard.writeText(url); toast.success('Share link copied.'); }
      catch { toast.error('Could not copy. The link is: ' + url); }
    };
    return (
      <>
        <p className="text-sm font-medium text-green-400">● Live</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <SmallBtn onClick={copy}>Copy share link</SmallBtn>
          <a href={`/catalog/track/${track.id}`} target="_blank" rel="noopener noreferrer"
            className="rounded-md border border-white/10 px-2.5 py-1 text-xs text-slate-300 hover:text-white">View page</a>
        </div>
      </>
    );
  }
  if (track.sync_status === 'needs_docs' || track.sync_status === 'cleared') {
    return (
      <>
        <p className="text-sm font-medium text-amber-400">● Needs docs</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-slate-400">
          {(track.sync_reasons || []).map((r) => <li key={r}>{reasonText(r)}</li>)}
        </ul>
      </>
    );
  }
  return <p className="text-sm font-medium text-cyan">● Processing</p>;
};

const TrackSyncPanel = ({ track, getToken, onUpdated, status }) => {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);       // 'bpm' | 'key' | 'moods'
  const [moodDraft, setMoodDraft] = useState([]);
  const [confirm, setConfirm] = useState(null);       // {scope, action}
  const [intake, setIntake] = useState(EMPTY_INTAKE);
  const meta = track.metadata || {};

  const run = useCallback(async (fn, success) => {
    setBusy(true);
    try {
      const updated = await fn();
      onUpdated({ ...track, ...updated });
      if (success) toast.success(success);
      return true;
    } catch (err) {
      toast.error(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }, [onUpdated, track]);

  const saveField = async (field, value) => {
    const ok = await run(() => api.patchMetadata(getToken, track.id, { [field]: value }), 'Saved.');
    if (ok) setEditing(null);
  };

  const applyConsent = async () => {
    const { scope, action } = confirm;
    const body = { scope, action };
    if (scope === 'sync' && action === 'grant') body.sync_intake = buildIntakePayload(intake);
    const ok = await run(() => api.changeConsent(getToken, track.id, body),
      action === 'grant' ? 'Turned on.' : 'Turned off.');
    if (ok) { setConfirm(null); setIntake(EMPTY_INTAKE); }
  };

  const toggle = (scope) => setConfirm({ scope, action: track.consent[scope] ? 'withdraw' : 'grant' });
  const addingSync = confirm?.scope === 'sync' && confirm?.action === 'grant';
  const copy = confirm && !addingSync ? CONFIRM_COPY[`${confirm.scope}:${confirm.action}`] : null;
  const isBuyoutGrant = confirm?.scope === 'exclusive_buyout' && confirm?.action === 'grant';
  const isExclusiveWithdraw = confirm?.scope === 'ai_exclusive' && confirm?.action === 'withdraw';
  const exclusiveEndMsg = `Exclusive AI training ends on ${fmtEndDate(new Date().toISOString())}. Your share returns to 33% for new AI licenses after that. Licenses already granted stay in place.`;
  const showBuyout = !!status?.buyouts_supported && !track.legacy;
  const modalTitle = addingSync ? 'Add to the OVOXI Catalog'
    : isBuyoutGrant ? 'Allow exclusive buyout?'
    : isExclusiveWithdraw ? 'Turn off exclusive AI training?' : copy?.[0];

  return (
    <div className="mt-4 grid grid-cols-1 gap-5 border-t border-white/10 pt-4 md:grid-cols-3" data-testid={`vault-panel-${track.id}`}>
      <div>
        <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">Uses</p>
        {[['ai_training', 'AI training'], ['sync', 'Sync placements']].map(([scope, label]) => (
          <div key={scope} className="flex items-center justify-between py-1 text-sm text-slate-300">
            {label}
            <Switch on={!!track.consent[scope]} label={label} disabled={busy} onClick={() => toggle(scope)} />
          </div>
        ))}
        {track.consent.ai_training && (
          <div className="mt-1 border-t border-white/10 pt-2" data-testid="ai-exclusive-toggle">
            <div className="flex items-center justify-between text-sm text-slate-300">
              <span>Exclusive to OVOXI</span>
              <Switch on={!!track.consent.ai_exclusive_chosen} label="Exclusive AI training" disabled={busy}
                onClick={() => setConfirm({ scope: 'ai_exclusive', action: track.consent.ai_exclusive_chosen ? 'withdraw' : 'grant' })} />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Exclusive means 50% instead of 33% on AI training sales of this song, and no AI training licensing elsewhere. Non-exclusive is the default.
            </p>
            {track.consent.ai_exclusive && track.consent.ai_exclusive_withdrawn_at && track.consent.ai_exclusive_in_effect && (
              <p className="mt-1 text-xs text-amber-300" data-testid="ai-exclusive-winddown">
                Exclusive AI training ends on {fmtEndDate(track.consent.ai_exclusive_withdrawn_at)}. Your share returns to 33% for new AI licenses after that. Licenses already granted stay in place.
              </p>
            )}
          </div>
        )}
        {showBuyout && (
          <div className="mt-1 border-t border-white/10 pt-2">
            <div className="flex items-center justify-between text-sm text-slate-300">
              <span>Allow exclusive buyout</span>
              <Switch on={!!track.consent.exclusive_buyout} label="Allow exclusive buyout"
                disabled={busy || !track.consent.sync} onClick={() => toggle('exclusive_buyout')} />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Buyers can request exclusive sync rights to this track. You get 50% of the buyout. During an exclusive term the track leaves the library and you can't license it for sync elsewhere. Turn off any time for future deals.
            </p>
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">Details</p>
        {['bpm', 'key'].map((field) => {
          const held = meta[`${field}_needs_confirmation`] === true && meta[field] != null;
          return (
            <div key={field} className="py-1 text-sm">
              <div className="flex items-center justify-between gap-2 text-slate-300">
                <span>{field === 'bpm' ? 'BPM' : 'Key'}</span>
                {editing === field ? (
                  <ValueEditor field={field} initial={meta[field]} busy={busy}
                    onSave={(v) => saveField(field, v)} onCancel={() => setEditing(null)} />
                ) : (
                  <span className="flex items-center gap-2">
                    <b className="font-medium text-white">{meta[field] ?? 'Not set'}</b>
                    <span className="text-[11px] text-slate-500">{sourceLabel(meta[`${field}_source`])}</span>
                    {!held && <SmallBtn onClick={() => setEditing(field)} disabled={busy}>Edit</SmallBtn>}
                  </span>
                )}
              </div>
              {held && editing !== field && (
                <div className="mt-1.5 rounded-lg border border-amber-400/35 bg-amber-400/[0.06] p-2.5" data-testid={`vault-held-${field}`}>
                  <p className="mb-2 text-xs text-amber-100"><HeldNote field={field} meta={meta} /></p>
                  <SmallBtn primary disabled={busy} onClick={() => saveField(field, meta[field])}>
                    {busy ? <Loader2 size={12} className="animate-spin" /> : `Confirm ${meta[field]}`}
                  </SmallBtn>{' '}
                  <SmallBtn disabled={busy} onClick={() => setEditing(field)}>Edit</SmallBtn>
                </div>
              )}
            </div>
          );
        })}
        <div className="py-1 text-sm text-slate-300">
          <div className="flex items-center justify-between gap-2">
            <span>Moods</span>
            {editing !== 'moods' && (
              <span className="flex items-center gap-2 text-right">
                <span className="text-white">{(meta.moods || []).join(', ') || 'Not set'}</span>
                <SmallBtn disabled={busy} onClick={() => { setMoodDraft(meta.moods || []); setEditing('moods'); }}>Edit</SmallBtn>
              </span>
            )}
          </div>
          {editing === 'moods' && (
            <div className="mt-2">
              <div className="flex flex-wrap gap-1.5">
                {MOODS.map((m) => {
                  const on = moodDraft.includes(m);
                  return (
                    <button key={m} type="button" aria-pressed={on}
                      onClick={() => setMoodDraft(on ? moodDraft.filter((x) => x !== m)
                        : moodDraft.length < MAX_MOODS ? [...moodDraft, m] : moodDraft)}
                      className={`rounded-full border px-2.5 py-0.5 text-xs ${on ? 'border-electric-light bg-electric/20 text-white' : 'border-white/10 text-slate-400'}`}>
                      {m}
                    </button>
                  );
                })}
              </div>
              <div className="mt-2 flex gap-2">
                <SmallBtn primary disabled={busy || moodDraft.length < 1} onClick={() => saveField('moods', moodDraft)}>Save</SmallBtn>
                <SmallBtn disabled={busy} onClick={() => setEditing(null)}>Cancel</SmallBtn>
              </div>
            </div>
          )}
        </div>
      </div>

      <div>
        <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">OVOXI Catalog</p>
        <SyncStatus track={track} />
      </div>

      <CosignBlock track={track} getToken={getToken} onUpdated={onUpdated} />

      <Modal open={!!confirm} onClose={() => !busy && setConfirm(null)} title={modalTitle}>
        {addingSync ? (
          <>
            <p className="mb-4 text-sm text-slate-400">
              Answer the sync questions. We check the track and list it automatically when it clears.
            </p>
            <SyncIntakeFields value={intake} onChange={setIntake} disabled={busy} />
          </>
        ) : isBuyoutGrant ? (
          <p className="text-sm text-slate-400">
            Buyers will be able to buy exclusive sync rights to <b className="font-medium text-white">{track.track_name}</b> without asking you first. You'll get 50% of each buyout and a notice within 5 business days. During an exclusive term the track leaves the library, and you can't license it for sync anywhere else (Artist Agreement section 3.4).
          </p>
        ) : isExclusiveWithdraw ? (
          <p className="text-sm text-slate-400">{exclusiveEndMsg}</p>
        ) : (
          <p className="text-sm text-slate-400">{copy?.[1]}</p>
        )}
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={applyConsent} disabled={busy || (addingSync && !isIntakeValid(intake))}
            className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {busy ? 'Saving…' : isBuyoutGrant ? 'Allow buyouts' : 'Confirm'}
          </button>
          <button type="button" onClick={() => setConfirm(null)} disabled={busy}
            className="rounded-full border border-white/10 px-5 py-2 text-sm text-slate-300">Cancel</button>
        </div>
      </Modal>
    </div>
  );
};

export default TrackSyncPanel;
