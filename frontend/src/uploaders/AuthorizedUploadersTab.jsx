import React, { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { errorMessage } from '../sync/api';
import AgreementDoc from '../agreement/AgreementDoc';
import { uploadersApi, USES, USE_SHORT, PERSON_ROLES, STATUS, shortDate } from './api';

// Brief 28 Part D1: Vault "Authorized uploaders" tab (artist only). List, Add uploader
// (a person, or OVOXI), then the auto-filled Upload Authorization and typed signature.
// Download PDF, Resend invite and Copy link wait for their endpoints (option A, Oct 29).

export const SCOPE_COPY =
  'Your uploader can upload songs and set the uses you check. Only you can take songs down, turn on Exclusive or see your Wallet.';

const EMPTY = { name: '', email: '', role: '', uses: [] };
const collapse = (s) => (s || '').trim().replace(/\s+/g, ' ');
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const labelCls = 'mb-1.5 block text-[13.5px] font-medium text-slate-300';
const inputCls = 'w-full rounded-lg border border-white/10 bg-black px-3 py-2.5 text-sm text-white focus:border-electric/70 focus:outline-none';
const ghostCls = 'rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300 transition-colors hover:border-electric/50 hover:text-white disabled:opacity-40';
const primaryCls = 'inline-flex items-center gap-2 rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(180,79,212,0.6)] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none';
const PILL = {
  ok: 'border-green-400/35 text-green-400',
  warn: 'border-amber-400/35 text-amber-400',
  off: 'border-white/10 text-slate-500',
};
const pillForUse = (u) => (u === 'sync' ? 'border-[#4FC3F7]/35 text-[#4FC3F7]' : 'border-electric/40 text-purple-300');

const Pill = ({ cls, children }) => (
  <span className={`mr-1 inline-block whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] ${cls}`}>{children}</span>
);

export default function AuthorizedUploadersTab({ getToken, legalName }) {
  const [rows, setRows] = useState(null);          // null while loading
  const [loadErr, setLoadErr] = useState('');
  const [view, setView] = useState('list');        // list | form | sign | sent
  const [kind, setKind] = useState('person');
  const [form, setForm] = useState(EMPTY);
  const [doc, setDoc] = useState(null);            // { blocks, text_sha256 }
  const [typedSig, setTypedSig] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [sent, setSent] = useState(null);
  const [revoking, setRevoking] = useState(null);

  const load = useCallback(async () => {
    try {
      setRows(await uploadersApi.list(getToken));
      setLoadErr('');
    } catch (e) {
      setRows([]);
      setLoadErr(errorMessage(e, 'Could not load your uploaders.'));
    }
  }, [getToken]);

  useEffect(() => { load(); }, [load]);

  const isOvoxi = kind === 'ovoxi';
  const ovoxiActive = (rows || []).some((r) => r.kind === 'ovoxi' && r.status === 'active');
  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleUse = (u) => setForm((f) => ({
    ...f, uses: f.uses.includes(u) ? f.uses.filter((x) => x !== u) : [...f.uses, u] }));

  const payload = () => (isOvoxi
    ? { kind, uses: USES.map(([u]) => u).filter((u) => form.uses.includes(u)) }
    : { kind, uploader_name: collapse(form.name), uploader_email: form.email.trim(),
        uploader_role: form.role, uses: USES.map(([u]) => u).filter((u) => form.uses.includes(u)) });

  const formError = () => {
    if (!isOvoxi) {
      if (!collapse(form.name)) return "Enter the uploader's name.";
      if (!EMAIL_RE.test(form.email.trim())) return 'Enter a valid uploader email.';
      if (!form.role) return 'Choose a role for the uploader.';
    }
    if (!form.uses.length) return 'Choose at least one use: Sync placements or AI training.';
    return '';
  };

  const startAdd = (k) => {
    setKind(k); setForm(EMPTY); setErr(''); setView('form');
  };

  const toReview = async () => {
    const e = formError();
    if (e) { setErr(e); return; }
    setBusy(true); setErr('');
    try {
      const data = await uploadersApi.preview(getToken, payload());
      setDoc({ blocks: data.blocks || [], text_sha256: data.text_sha256 });
      setTypedSig(''); setAgreed(false); setView('sign');
    } catch (ex) {
      setErr(errorMessage(ex));
    } finally { setBusy(false); }
  };

  const nameMatches = !legalName || collapse(typedSig).toLowerCase() === collapse(legalName).toLowerCase();
  const canSign = !!collapse(typedSig) && nameMatches && agreed && !busy;

  const sign = async () => {
    setBusy(true); setErr('');
    try {
      const created = await uploadersApi.create(getToken, {
        ...payload(), typed_signature: collapse(typedSig), text_sha256: doc.text_sha256, consent_electronic: true });
      if (isOvoxi) {
        toast.success('OVOXI is now an uploader for your account.');
        setView('list');
      } else {
        setSent(created); setView('sent');
      }
      load();
    } catch (ex) {
      setErr(errorMessage(ex));
    } finally { setBusy(false); }
  };

  const confirmRevoke = async () => {
    setBusy(true);
    try {
      await uploadersApi.revoke(getToken, revoking.id);
      toast.success(revoking.status === 'active' ? 'Uploader revoked.' : 'Invite cancelled.');
      setRevoking(null);
      load();
    } catch (ex) {
      toast.error(errorMessage(ex));
    } finally { setBusy(false); }
  };

  const who = (r) => (r.kind === 'ovoxi' ? 'OVOXI, Inc.' : r.uploader_name);
  const shortName = (r) => (r.kind === 'ovoxi' ? 'OVOXI' : (r.uploader_name || '').split(' ')[0]);

  // ---- Form: who they are and what they can set ----
  if (view === 'form') {
    return (
      <div className="max-w-2xl" data-testid="uploader-form">
        <button type="button" onClick={() => setView('list')} className="text-sm text-[#4FC3F7] hover:underline">&larr; Back to uploaders</button>
        <h2 className="mt-3 font-heading text-2xl font-semibold text-white">{isOvoxi ? 'Add OVOXI as uploader' : 'Add an uploader'}</h2>
        <p className="mb-5 mt-1 text-sm text-slate-400">
          {isOvoxi
            ? 'Step 1 of 2. OVOXI staff can upload your songs for you. Every action records which staff member took it.'
            : 'Step 1 of 2: who they are and what they can set.'}
        </p>
        <div className="mb-4 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          {!isOvoxi && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="mb-4">
                  <label className={labelCls} htmlFor="up-name">Name or company</label>
                  <input id="up-name" type="text" className={inputCls} value={form.name} onChange={(e) => setField('name', e.target.value)} />
                </div>
                <div className="mb-4">
                  <label className={labelCls} htmlFor="up-email">Email</label>
                  <input id="up-email" type="email" className={inputCls} value={form.email} onChange={(e) => setField('email', e.target.value)} />
                  <p className="mt-1 text-xs text-slate-500">They sign in with this email to accept.</p>
                </div>
              </div>
              <div className="mb-4">
                <label className={labelCls} htmlFor="up-role">Role</label>
                <select id="up-role" className={inputCls} value={form.role} onChange={(e) => setField('role', e.target.value)}>
                  <option value="">Choose a role</option>
                  {PERSON_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
            </>
          )}
          <div className={labelCls}>{isOvoxi ? 'Which uses can OVOXI set?' : 'Which uses can they set?'}</div>
          {USES.map(([u, label]) => (
            <label key={u} className="mb-2 flex cursor-pointer items-start gap-2.5 rounded-xl border border-white/10 p-3">
              <input type="checkbox" data-use={u} className="mt-1 accent-[#9B59D4]" checked={form.uses.includes(u)} onChange={() => toggleUse(u)} />
              <span>
                <span className="block text-sm font-medium text-white">{label}</span>
                <span className="block text-[12.5px] text-slate-400">
                  {u === 'sync'
                    ? `${isOvoxi ? 'OVOXI' : 'They'} can list your songs in the OVOXI sync library.`
                    : `${isOvoxi ? 'OVOXI' : 'They'} can license your songs to AI companies as training data.`}
                </span>
              </span>
            </label>
          ))}
          <p className="text-xs text-slate-500">Pick at least one. Exclusive is never available to uploaders.</p>
          <div className="mt-4 rounded-xl border border-[#4FC3F7]/30 bg-[#4FC3F7]/[0.06] p-3.5 text-sm text-sky-100">{SCOPE_COPY}</div>
        </div>
        <div className="min-h-[18px] text-[13px] text-red-400" role="alert">{err}</div>
        <div className="mt-2 flex justify-end gap-2">
          <button type="button" className={ghostCls} onClick={() => setView('list')}>Cancel</button>
          <button type="button" className={primaryCls} onClick={toReview} disabled={busy}>
            {busy && <Loader2 size={16} className="animate-spin" />}Review and sign
          </button>
        </div>
      </div>
    );
  }

  // ---- Sign: the auto-filled Authorization and the typed signature ----
  if (view === 'sign') {
    return (
      <div className="max-w-2xl" data-testid="uploader-sign">
        <button type="button" onClick={() => setView('form')} className="text-sm text-[#4FC3F7] hover:underline">&larr; Edit details</button>
        <h2 className="mt-3 font-heading text-2xl font-semibold text-white">Sign the Upload Authorization</h2>
        <p className="mb-4 mt-1 text-sm text-slate-400">
          {isOvoxi
            ? 'Step 2 of 2. Read it, then type your full legal name to sign. It takes effect when you sign.'
            : `Step 2 of 2. Read it, then type your full legal name to sign. ${shortName({ uploader_name: collapse(form.name) })} signs next, then it takes effect.`}
        </p>
        <div tabIndex={0} aria-label="Upload Authorization text"
          className="h-[340px] overflow-auto rounded-xl border border-white/10 bg-white px-6 py-[22px] font-serif text-[13.5px] leading-[1.55] text-[#111]">
          <AgreementDoc blocks={doc?.blocks || []} />
        </div>
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          <label className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
            <input type="checkbox" data-testid="agree" className="mt-1 accent-[#9B59D4]" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
            <span>I have read the Upload Authorization and agree to it. I agree to sign electronically, and that my typed name is my legal signature.</span>
          </label>
          <div className="mt-4">
            <label className={labelCls} htmlFor="up-sig">Type your full legal name to sign</label>
            <input id="up-sig" type="text" autoComplete="off" className={inputCls} placeholder={legalName || ''}
              value={typedSig} onChange={(e) => setTypedSig(e.target.value)} />
            <div className={`my-1.5 flex min-h-[52px] items-end border-b border-white/10 px-0.5 py-1.5 font-serif text-[28px] italic ${collapse(typedSig) ? 'text-white' : 'text-[#333]'}`}>
              {collapse(typedSig) || 'Your signature'}
            </div>
            {legalName && (
              <p className="text-xs text-slate-500">Must match the licensor name on your Artist Agreement: <b className="font-medium text-slate-300">{legalName}</b></p>
            )}
          </div>
        </div>
        <div className="min-h-[18px] text-[13px] text-red-400" role="alert">
          {err || (collapse(typedSig) && !nameMatches ? 'The name must match your legal name exactly.' : '')}
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <button type="button" className={ghostCls} onClick={() => setView('list')} disabled={busy}>Cancel</button>
          <button type="button" className={primaryCls} onClick={sign} disabled={!canSign}>
            {busy && <Loader2 size={16} className="animate-spin" />}
            {isOvoxi ? 'Sign and add OVOXI' : `Sign and send to ${shortName({ uploader_name: collapse(form.name) })}`}
          </button>
        </div>
      </div>
    );
  }

  // ---- Sent: waiting for the uploader ----
  if (view === 'sent' && sent) {
    return (
      <div className="max-w-2xl rounded-2xl border border-white/10 bg-white/[0.02] px-6 py-9 text-center" data-testid="uploader-sent">
        <div className="mb-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">Signed by you</div>
        <h2 className="font-heading text-2xl font-semibold text-white">Waiting for {shortName(sent)} to sign</h2>
        <p className="mx-auto mb-5 mt-2 max-w-md text-sm text-slate-400">
          We emailed {sent.uploader_email} a link to sign. {shortName(sent)} can upload for you as soon as they sign.
        </p>
        <button type="button" className={primaryCls} onClick={() => setView('list')}>Back to uploaders</button>
      </div>
    );
  }

  // ---- List ----
  if (rows === null) {
    return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-electric" size={32} /></div>;
  }

  const addButtons = (
    <div className="flex flex-wrap gap-2">
      {!ovoxiActive && <button type="button" className={ghostCls} onClick={() => startAdd('ovoxi')}>Add OVOXI as uploader</button>}
      <button type="button" className={primaryCls} onClick={() => startAdd('person')}>+ Add uploader</button>
    </div>
  );

  return (
    <div data-testid="uploaders-list">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-2xl font-semibold text-white">Authorized uploaders</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">{SCOPE_COPY}</p>
        </div>
        {rows.length > 0 && addButtons}
      </div>
      {loadErr && <div className="mb-4 rounded-xl border border-red-400/35 bg-red-400/[0.06] p-3 text-sm text-red-200" role="alert">{loadErr}</div>}

      {rows.length === 0 && !loadErr ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] px-6 py-10 text-center">
          <h3 className="mb-2 font-heading text-lg text-white">No uploaders yet</h3>
          <p className="mx-auto mb-5 max-w-md text-sm text-slate-400">Let your engineer, studio, producer or manager upload songs for you, without sharing your login.</p>
          <div className="flex justify-center">{addButtons}</div>
        </div>
      ) : rows.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-white/[0.02] px-2 py-1">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-[0.12em] text-slate-500">
                  {['Name', 'Role', 'Uses', 'Status', 'Date', ''].map((h) => (
                    <th key={h} className="border-b border-white/10 px-2.5 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const [label, tone] = STATUS[r.status] || ['Ended', 'off'];
                  const live = r.status === 'active' || r.status === 'awaiting_uploader';
                  return (
                    <tr key={r.id} data-testid={`uploader-${r.id}`} className="align-top">
                      <td className="border-b border-white/10 px-2.5 py-3">
                        <div className={`font-medium ${live ? 'text-white' : 'text-slate-500'}`}>{who(r)}</div>
                        <div className="text-xs text-slate-500">{r.kind === 'ovoxi' ? 'Acts through OVOXI staff' : r.uploader_email}</div>
                      </td>
                      <td className="border-b border-white/10 px-2.5 py-3 text-slate-300">{r.kind === 'ovoxi' ? 'OVOXI' : r.uploader_role}</td>
                      <td className="border-b border-white/10 px-2.5 py-3">
                        {(r.uses || []).map((u) => <Pill key={u} cls={live ? pillForUse(u) : PILL.off}>{USE_SHORT[u] || u}</Pill>)}
                      </td>
                      <td className="border-b border-white/10 px-2.5 py-3">
                        <Pill cls={PILL[tone]}>{r.status === 'revoked' && r.revoked_at ? `Revoked ${shortDate(r.revoked_at)}` : label}</Pill>
                      </td>
                      <td className="whitespace-nowrap border-b border-white/10 px-2.5 py-3 text-slate-300">{shortDate(r.created_at)}</td>
                      <td className="whitespace-nowrap border-b border-white/10 px-2.5 py-3 text-right">
                        {live && (
                          <button type="button" onClick={() => setRevoking(r)} className="text-sm text-red-400 hover:underline">
                            {r.status === 'active' ? 'Revoke' : 'Cancel invite'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-slate-500">To change an uploader's uses, revoke them and add them again with the new uses. Songs they already uploaded stay in your catalog.</p>
        </>
      )}

      {revoking && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" role="dialog" aria-modal="true" aria-labelledby="revoke-title">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0A0A0C] p-6">
            <h4 id="revoke-title" className="mb-2 font-heading text-lg text-white">
              {revoking.status === 'active' ? `Revoke ${who(revoking)}?` : `Cancel the invite to ${who(revoking)}?`}
            </h4>
            <p className="mb-4 text-sm text-slate-400">
              {revoking.status === 'active'
                ? `${shortName(revoking)} can no longer upload or edit songs for you, starting now. Songs ${shortName(revoking)} already uploaded stay in your catalog with their current uses. You can remove them yourself.`
                : 'The signing link stops working. Nothing was uploaded under this invite.'}
            </p>
            <div className="flex justify-end gap-2">
              <button type="button" className={ghostCls} onClick={() => setRevoking(null)} disabled={busy}>Keep</button>
              <button type="button" onClick={confirmRevoke} disabled={busy} data-testid="confirm-revoke"
                className="rounded-full bg-red-400 px-5 py-2 text-sm font-semibold text-[#0A0A0C] disabled:opacity-40">
                {revoking.status === 'active' ? 'Revoke' : 'Cancel invite'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
