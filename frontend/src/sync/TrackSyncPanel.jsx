import React, { useCallback, useState } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import Modal from './Modal';
import SyncIntakeFields, { EMPTY_INTAKE, buildIntakePayload, isIntakeValid } from './SyncIntakeFields';
import DeclarationsFields from '../upload/DeclarationsFields';
import { EMPTY_DECLARATIONS, buildDeclarationsPayload, declarationsMissing, licenseFileProblem } from '../upload/declarations';
import { api, errorMessage } from './api';
import { PENDING_REASONS, reasonText } from './labels';
import {
  BPM_MAX, BPM_MIN, LOOPS_NO_AI_MESSAGE, MAJOR_KEYS, MAX_MOODS, MINOR_KEYS, MOODS,
} from './constants';

// Per-track "Uses and details" panel in the Vault (PRD-03 4.2, 4.3, 4.4).

const CONFIRM_COPY = {
  'ai_training:grant': ['Use this track for AI training?', 'It will be included in future AI deliveries.'],
  'ai_training:withdraw': ['Stop using this track for AI training?',
    'It will be left out of future AI deliveries. Deliveries already made are not recalled.'],
  'sync:withdraw': ['Remove from sync placements?',
    'It will no longer be listed for sync. Licenses already sold stay valid.'],
  // Brief 25b C3: one Exclusive switch per song.
  'exclusive:grant': ['Offer this song as exclusive?',
    'It will no longer be sold to multiple buyers. Buyers can request to license it outright for sync, AI training or both.'],
  'exclusive:withdraw': ['Stop offering this song as exclusive?',
    'It returns to standard licensing for any use not already sold exclusively.'],
};

const EXCLUSIVE_COPY = {
  off: 'Non-exclusive. Multiple buyers can license this song.',
  on: 'Exclusive. Give an option for buyers to purchase this license outright for a higher price.',
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

// One catalog line per use (Brief 25b C5): Live, Pending checks, Needs info, Processing.
const UseStatus = ({ track, use, label }) => {
  const status = use === 'sync' ? track.sync_status : track.ai_status;
  const reasons = (use === 'sync' ? track.sync_reasons : track.ai_reasons) || [];
  const sold = (track.consent.exclusive_sold || {})[use];
  let line;
  if (sold) {
    line = <span className="text-cyan">● Licensed exclusively</span>;
  } else if (track.status === 'CONFLICT' || status === 'conflict') {
    line = <span className="text-red-400">● Conflict: this recording appears to match existing copyrighted material</span>;
  } else if (status === 'cleared' && track.on_sync_profile) {
    line = <span className="text-green-400">● Live in the OVOXI Catalog</span>;
  } else if (!status) {
    line = <span className="text-cyan">● Processing</span>;
  } else if (reasons.length && reasons.every((r) => PENDING_REASONS.includes(r))) {
    line = <span className="text-amber-300">● Pending checks</span>;
  } else {
    line = <span className="text-amber-400">● Needs info</span>;
  }
  return (
    <div className="py-1" data-testid={`vault-status-${use}-${track.id}`}>
      <p className="text-sm font-medium"><span className="text-slate-400">{label}: </span>{line}</p>
      {!sold && status && status !== 'cleared' && reasons.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-slate-400">
          {reasons.map((r) => <li key={r}>{reasonText(r)}</li>)}
        </ul>
      )}
    </div>
  );
};

const CatalogStatus = ({ track }) => {
  if (track.awaiting_approval) {
    return (
      <>
        <p className="text-sm font-medium text-amber-300" data-testid={`vault-awaiting-${track.id}`}>● Waiting for account approval</p>
        <p className="mt-1 text-xs text-slate-500">Received. We process and list it once your artist account is approved.</p>
      </>
    );
  }
  if (!track.consent.sync && !track.consent.ai_training) {
    return (
      <>
        <p className="text-sm text-slate-500">Not in the OVOXI Catalog</p>
        <p className="mt-1 text-xs text-slate-500">Turn on Sync placements or AI training to add it.</p>
      </>
    );
  }
  if (track.delisted_by_admin) {
    return (
      <>
        <p className="text-sm font-medium text-red-400">● Removed by OVOXI</p>
        <p className="mt-1 text-xs text-slate-500">Contact support if you think this is a mistake.</p>
      </>
    );
  }
  const live = (track.sync_status === 'cleared' || track.ai_status === 'cleared') && track.on_sync_profile;
  const url = `${window.location.origin}/catalog/track/${track.id}`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); toast.success('Share link copied.'); }
    catch { toast.error('Could not copy. The link is: ' + url); }
  };
  return (
    <>
      {track.consent.sync && <UseStatus track={track} use="sync" label="Sync" />}
      {track.consent.ai_training && <UseStatus track={track} use="ai" label="AI training" />}
      {live && (
        <div className="mt-2 flex flex-wrap gap-2">
          <SmallBtn onClick={copy}>Copy share link</SmallBtn>
          <a href={`/catalog/track/${track.id}`} target="_blank" rel="noopener noreferrer"
            className="rounded-md border border-white/10 px-2.5 py-1 text-xs text-slate-300 hover:text-white">View page</a>
        </div>
      )}
    </>
  );
};

const LOOP_REVIEW_TEXT = {
  pending: 'OVOXI reviews each loop license before the song is listed.',
  approved: 'Loop licenses approved.',
  rejected: 'A loop license was not accepted. Contact us.',
};

// Agreement 3.6: the song's loops, with a license upload for each.
const LoopsBlock = ({ track, getToken, onUpdated }) => {
  const [busy, setBusy] = useState(null);
  const loops = track.loops || [];
  if (!loops.length) return null;
  const upload = async (i, file) => {
    const problem = licenseFileProblem(file);
    if (!file) return;
    if (problem) { toast.error(problem); return; }
    setBusy(i);
    try {
      const updated = await api.uploadLoopLicense(getToken, track.id, i, file);
      onUpdated({ ...track, ...updated });
      toast.success('License uploaded.');
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(null); }
  };
  return (
    <div className="md:col-span-3 border-t border-white/10 pt-3" data-testid={`vault-loops-${track.id}`}>
      <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">Loops (sync only)</p>
      <ul className="space-y-1.5">
        {loops.map((lp, i) => (
          <li key={i} className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-300">
            <span><b className="font-medium text-white">{lp.loop_name}</b> by {lp.creator_name} ({lp.source})</span>
            <span className="flex items-center gap-2">
              <span className={`text-xs ${lp.has_license ? 'text-green-400' : 'text-amber-400'}`}>
                {lp.has_license ? 'License on file' : 'License needed'}
              </span>
              <label className="cursor-pointer rounded-md border border-white/10 px-2.5 py-1 text-xs text-slate-300 hover:text-white">
                {busy === i ? 'Uploading…' : lp.has_license ? 'Replace license' : 'Upload license'}
                <input type="file" className="hidden" disabled={busy !== null}
                  accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                  onChange={(e) => { upload(i, e.target.files?.[0]); e.target.value = ''; }} />
              </label>
            </span>
          </li>
        ))}
      </ul>
      {track.loop_license_status && (
        <p className="mt-2 text-xs text-slate-500">{LOOP_REVIEW_TEXT[track.loop_license_status]}</p>
      )}
    </div>
  );
};

const TrackSyncPanel = ({ track, getToken, onUpdated, status }) => {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);       // 'bpm' | 'key' | 'moods'
  const [moodDraft, setMoodDraft] = useState([]);
  const [confirm, setConfirm] = useState(null);       // {scope, action}
  const [intake, setIntake] = useState(EMPTY_INTAKE);
  const [proNotice, setProNotice] = useState(false);
  const [declaring, setDeclaring] = useState(false);
  const [decl, setDecl] = useState(EMPTY_DECLARATIONS);
  const meta = track.metadata || {};
  const loopSong = (track.loops || []).length > 0;

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
    if (ok) { setConfirm(null); setIntake(EMPTY_INTAKE); setProNotice(false); }
  };

  const saveDeclarations = async () => {
    const ok = await run(() => api.setDeclarations(getToken, track.id, buildDeclarationsPayload(decl)), 'Saved.');
    if (ok) { setDeclaring(false); setDecl(EMPTY_DECLARATIONS); }
  };

  const toggle = (scope) => setConfirm({ scope, action: track.consent[scope] ? 'withdraw' : 'grant' });
  const addingSync = confirm?.scope === 'sync' && confirm?.action === 'grant';
  const copy = confirm && !addingSync ? CONFIRM_COPY[`${confirm.scope}:${confirm.action}`] : null;
  const showExclusive = !track.legacy && (!!status?.exclusive_supported || !!track.consent.exclusive);
  const modalTitle = addingSync ? 'Add sync placements' : copy?.[0];
  const declMissing = declarationsMissing(decl);

  return (
    <div className="mt-4 grid grid-cols-1 gap-5 border-t border-white/10 pt-4 md:grid-cols-3" data-testid={`vault-panel-${track.id}`}>
      <div>
        <p className="mb-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">Uses</p>
        {[['sync', 'Sync placements'], ['ai_training', 'AI training']].map(([scope, label]) => {
          const blocked = scope === 'ai_training' && loopSong && !track.consent.ai_training;
          return (
            <div key={scope} className="py-1 text-sm text-slate-300">
              <div className="flex items-center justify-between">
                {label}
                <Switch on={!!track.consent[scope]} label={label} disabled={busy || blocked} onClick={() => toggle(scope)} />
              </div>
              {blocked && <p className="mt-1 text-xs text-slate-500">{LOOPS_NO_AI_MESSAGE}</p>}
            </div>
          );
        })}
        {showExclusive && (track.consent.sync || track.consent.ai_training) && (
          <div className="mt-1 border-t border-white/10 pt-2" data-testid={`vault-exclusive-${track.id}`}>
            <div className="flex items-center justify-between text-sm text-slate-300">
              <span>Exclusive</span>
              <Switch on={!!track.consent.exclusive} label="Exclusive" disabled={busy}
                onClick={() => toggle('exclusive')} />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {track.consent.exclusive ? EXCLUSIVE_COPY.on : EXCLUSIVE_COPY.off}
            </p>
          </div>
        )}
        {track.needs_declarations && !track.legacy && (
          <div className="mt-2 rounded-lg border border-amber-400/35 bg-amber-400/[0.06] p-2.5" data-testid={`vault-declare-${track.id}`}>
            <p className="mb-2 text-xs text-amber-100">Answer two questions about this song: samples and loops, and AI tools.</p>
            <SmallBtn primary disabled={busy} onClick={() => setDeclaring(true)}>Answer now</SmallBtn>
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
        <CatalogStatus track={track} />
      </div>

      <LoopsBlock track={track} getToken={getToken} onUpdated={onUpdated} />
      <CosignBlock track={track} getToken={getToken} onUpdated={onUpdated} />

      <Modal open={declaring} onClose={() => !busy && setDeclaring(false)} title="About this song">
        <DeclarationsFields value={decl} onChange={setDecl} disabled={busy} idPrefix={`vault-decl-${track.id}`} />
        {decl.samples === 'royalty_free_loop' && (
          <p className="mt-3 text-xs text-slate-500">After saving, upload each loop license from this song's panel.</p>
        )}
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={saveDeclarations} disabled={busy || declMissing.length > 0}
            className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {busy ? 'Saving…' : 'Save'}
          </button>
          <button type="button" onClick={() => setDeclaring(false)} disabled={busy}
            className="rounded-full border border-white/10 px-5 py-2 text-sm text-slate-300">Cancel</button>
        </div>
      </Modal>

      <Modal open={!!confirm} onClose={() => !busy && setConfirm(null)} title={modalTitle}>
        {addingSync ? (
          <>
            <p className="mb-4 text-sm text-slate-400">
              Answer the sync questions. We check the track and list it automatically when it clears.
            </p>
            {track.needs_declarations ? (
              <p className="text-sm text-amber-200">Answer the samples and AI tools questions for this song first.</p>
            ) : (
              <SyncIntakeFields value={intake} onChange={setIntake} disabled={busy}
                notAffiliated={proNotice} onNotAffiliated={(v) => setProNotice(v)} />
            )}
          </>
        ) : (
          <p className="text-sm text-slate-400">{copy?.[1]}</p>
        )}
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={applyConsent}
            disabled={busy || (addingSync && (track.needs_declarations || proNotice || !isIntakeValid(intake)))}
            className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {busy ? 'Saving…' : 'Confirm'}
          </button>
          <button type="button" onClick={() => { setConfirm(null); setProNotice(false); }} disabled={busy}
            className="rounded-full border border-white/10 px-5 py-2 text-sm text-slate-300">Cancel</button>
        </div>
      </Modal>
    </div>
  );
};

export default TrackSyncPanel;
