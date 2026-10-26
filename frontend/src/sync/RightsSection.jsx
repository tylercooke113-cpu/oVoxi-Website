import React from 'react';
import { X } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  IPI_MESSAGE,
  IPI_PATTERN,
  IPI_PLACEHOLDER,
  cleanIpi,
  MAX_PARTIES,
  PRO_ORGS,
  PUBLISHER_ROLES,
  TOTAL_BP,
  WRITER_ROLES,
} from './constants';

// Splits for every upload. PRD-02 rights model, PRD-03 section 4.1 (check 1).
// Brief 22 C1: paired writer/publisher cards, plus a signing email on every
// rights holder who is not the uploader. Shares are typed as percentages and
// sent as integer basis points. The card pairing is display only: buildRightsPayload
// flattens back to three flat lists (writers, publishers, master_owners).

// Permissive email check, matching backend/rights.py EMAIL_PATTERN.
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const NO_PRO = 'none';

const newPublisher = () => ({ legal_name: '', pct: '', role: 'E', society: '', ipi: '', email: '' });

const newWriter = (legalName = '') => ({
  legal_name: legalName, pct: '', role: 'CA', society: '', ipi: '', email: '',
  no_publisher: false,
  publishers: [newPublisher()],
});

const newOwner = () => ({ legal_name: '', pct: '', role: null, society: '', ipi: '', email: '' });

export const emptyRights = () => ({
  owns_everything: false,
  self_legal_name: '',
  legal_name_touched: false,
  account_legal_name: '',     // licensor on the signed agreement (Oct 26); never sent
  writers: [newWriter()],
  master_owners: [newOwner()],
  attested: false,
});

export const toBp = (pct) => {
  const n = parseFloat(pct);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
};

const fmtPct = (bp) => (bp / 100).toFixed(2).replace(/\.?0+$/, '');

const sumBp = (parties) => parties.reduce((s, p) => s + toBp(p.pct), 0);

// Every publisher row across all writers that still have a publisher (display pairing
// is dropped here; the payload is a single flat list).
const flatPublishers = (r) => r.writers.flatMap((w) => (w.no_publisher ? [] : w.publishers));

const isSelf = (p, selfCf) => p.legal_name.trim().toLowerCase() === selfCf;

const partyProblem = (parties, selfCf, { email = true } = {}) => {
  if (parties.length < 1 || parties.length > MAX_PARTIES) return true;
  if (parties.some((p) => !p.legal_name.trim() || toBp(p.pct) < 1)) return true;
  if (parties.some((p) => p.ipi && !IPI_PATTERN.test(p.ipi))) return true;
  // Everyone who is not the uploader needs a valid signing email.
  if (email && parties.some((p) => !isSelf(p, selfCf) && !EMAIL_RE.test(p.email.trim()))) return true;
  const names = parties.map((p) => p.legal_name.trim().toLowerCase());
  if (new Set(names).size !== names.length) return true;
  return sumBp(parties) !== TOTAL_BP;
};

// Brief 25b C2 (Agreement 3.5): with sync on, every writer needs a PRO and an IPI.
// "Other" also needs the PRO's name.
export const writersMissingPro = (r) => (r.owns_everything ? []
  : r.writers.filter((w) => !w.society || !IPI_PATTERN.test(w.ipi || '')
    || (w.society === 'Other' && !(w.society_other || '').trim())));

const normName = (v) => (v || '').split(/\s+/).filter(Boolean).join(' ').toLowerCase();

// Oct 26: the uploader's legal name must be the one on their signed agreement.
export const legalNameMismatch = (r) => !!r.account_legal_name
  && normName(r.self_legal_name) !== normName(r.account_legal_name);
export const LEGAL_NAME_MISMATCH = 'This does not match the legal name on your account.';

// Lower-cased signing emails of everyone in the splits who is not the uploader. Loop
// creators must appear here with the same email (Agreement 3.6(a)).
export const rightsEmails = (r) => {
  if (r.owns_everything) return [];
  const selfCf = r.self_legal_name.trim().toLowerCase();
  return [...r.writers, ...flatPublishers(r), ...r.master_owners]
    .filter((p) => !isSelf(p, selfCf) && p.email.trim())
    .map((p) => p.email.trim().toLowerCase());
};

export const isRightsValid = (r, { requirePro = false } = {}) => {
  if (!r.self_legal_name.trim() || !r.attested) return false;
  if (legalNameMismatch(r)) return false;
  if (r.owns_everything) return true;
  const selfCf = r.self_legal_name.trim().toLowerCase();
  if (requirePro && writersMissingPro(r).length) return false;
  if (partyProblem(r.writers, selfCf)) return false;
  if (partyProblem(flatPublishers(r), selfCf)) return false;
  if (partyProblem(r.master_owners, selfCf)) return false;
  return true;
};

export const buildRightsPayload = (r) => {
  const selfCf = r.self_legal_name.trim().toLowerCase();
  const emailFor = (p) => (isSelf(p, selfCf) ? null : (p.email.trim() || null));
  const writerRow = (p) => ({
    legal_name: p.legal_name.trim(), share_bp: toBp(p.pct), role: p.role,
    society: p.society || null, ipi_name_number: p.ipi || null, email: emailFor(p),
    society_other: p.society === 'Other' ? (p.society_other || '').trim() || null : null,
  });
  const publisherRow = (p) => ({
    legal_name: p.legal_name.trim(), share_bp: toBp(p.pct), role: p.role,
    society: null, ipi_name_number: null, email: emailFor(p),
  });
  const ownerRow = (p) => ({
    legal_name: p.legal_name.trim(), share_bp: toBp(p.pct), role: null,
    society: null, ipi_name_number: null, email: emailFor(p),
  });
  return {
    owns_everything: r.owns_everything,
    self_legal_name: r.self_legal_name.trim(),
    writers: r.owns_everything ? [] : r.writers.map(writerRow),
    publishers: r.owns_everything ? [] : flatPublishers(r).map(publisherRow),
    master_owners: r.owns_everything ? [] : r.master_owners.map(ownerRow),
    attested: r.attested,
  };
};

const CHECKBOX_CLASS =
  'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white focus-visible:ring-electric';
const FIELD_CLASS =
  'border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric';
const SMALL_BTN =
  'rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 transition-colors hover:border-electric/40 hover:text-white disabled:opacity-40';
const CARD = 'space-y-3 rounded-xl border border-white/10 bg-ink p-4';

const cleanPct = (raw) => {
  const s = raw.replace(/[^0-9.]/g, '');
  const [whole, ...rest] = s.split('.');
  return rest.length ? `${whole}.${rest.join('').slice(0, 2)}` : whole;
};

const ShareInput = ({ label, value, onChange, disabled }) => (
  <div className="space-y-1">
    <span className="text-[11px] text-slate-500">{label}</span>
    <div className="relative">
      <Input
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(cleanPct(e.target.value))}
        placeholder="0"
        disabled={disabled}
        className={`${FIELD_CLASS} pr-6 text-right`}
      />
      <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-sm text-slate-500">%</span>
    </div>
  </div>
);

const EmailInput = ({ value, onChange, disabled, testid }) => (
  <div className="space-y-1">
    <span className="text-[11px] text-slate-500">Email for signing</span>
    <Input
      type="email"
      data-testid={testid}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      maxLength={254}
      placeholder="name@example.com"
      disabled={disabled}
      className={FIELD_CLASS}
    />
    {value.trim() && !EMAIL_RE.test(value.trim()) && (
      <p className="text-xs text-red-400">Enter a valid email.</p>
    )}
  </div>
);

const TotalLine = ({ label, parties }) => {
  const total = sumBp(parties);
  const ok = total === TOTAL_BP;
  return (
    <p className={`text-xs ${ok ? 'text-green-400' : 'text-red-400'}`}>
      {label}: {fmtPct(total)}% (must total 100%)
      {ok ? ' ✓' : total < TOTAL_BP ? `, ${fmtPct(TOTAL_BP - total)}% left` : `, ${fmtPct(total - TOTAL_BP)}% over`}
    </p>
  );
};

const RightsSection = ({ value, onChange, disabled, requirePro = false }) => {
  const r = value;
  const set = (patch) => onChange({ ...r, ...patch });
  const selfCf = r.self_legal_name.trim().toLowerCase();
  const publishers = flatPublishers(r);

  const setWriter = (i, patch) =>
    set({ writers: r.writers.map((w, idx) => (idx === i ? { ...w, ...patch } : w)) });

  const setPublisher = (wi, pi, patch) =>
    setWriter(wi, {
      publishers: r.writers[wi].publishers.map((p, idx) => (idx === pi ? { ...p, ...patch } : p)),
    });

  const setOwner = (i, patch) =>
    set({ master_owners: r.master_owners.map((o, idx) => (idx === i ? { ...o, ...patch } : o)) });

  const addWriter = () => {
    if (r.writers.length >= MAX_PARTIES) return;
    // Pair the new writer with a publisher unless the publisher side is already full.
    const writer = newWriter();
    if (publishers.length >= MAX_PARTIES) writer.no_publisher = true;
    set({ writers: [...r.writers, writer] });
  };
  const removeWriter = (i) => {
    if (r.writers.length > 1) set({ writers: r.writers.filter((_, idx) => idx !== i) });
  };

  const addPublisher = (wi) => {
    if (publishers.length >= MAX_PARTIES) return;
    setWriter(wi, { publishers: [...r.writers[wi].publishers, newPublisher()] });
  };
  const removePublisher = (wi, pi) => {
    const list = r.writers[wi].publishers;
    if (list.length > 1) setWriter(wi, { publishers: list.filter((_, idx) => idx !== pi) });
  };
  const toggleNoPublisher = (wi, checked) =>
    setWriter(wi, { no_publisher: checked, publishers: checked ? [] : [newPublisher()] });

  const addOwner = () => {
    if (r.master_owners.length < MAX_PARTIES) set({ master_owners: [...r.master_owners, newOwner()] });
  };
  const removeOwner = (i) => {
    if (r.master_owners.length > 1) set({ master_owners: r.master_owners.filter((_, idx) => idx !== i) });
  };

  return (
    <div className="space-y-4" data-testid="upload-rights">
      <Label className="text-slate-300">Who owns this song? *</Label>

      <label
        htmlFor="rights-own"
        className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3.5 transition-colors ${
          r.owns_everything ? 'border-electric/60 bg-electric/[0.06]' : 'border-white/10 hover:border-electric/35'
        }`}
      >
        <Checkbox
          id="rights-own"
          data-testid="upload-rights-own"
          checked={r.owns_everything}
          onCheckedChange={(v) => set({ owns_everything: v === true })}
          disabled={disabled}
          className={CHECKBOX_CLASS}
        />
        <span className="text-sm font-medium text-white">
          I own 100% of the writing, publishing and master of this song.
        </span>
      </label>

      <div className="space-y-2">
        <Label htmlFor="rights-legal-name" className="text-slate-300">Your legal name *</Label>
        <Input
          id="rights-legal-name"
          data-testid="upload-rights-legal-name"
          value={r.self_legal_name}
          onChange={(e) => set({ self_legal_name: e.target.value, legal_name_touched: true })}
          maxLength={120}
          placeholder="Full legal name"
          disabled={disabled}
          className={FIELD_CLASS}
        />
        {legalNameMismatch(r) ? (
          <p className="text-xs text-red-400" data-testid="upload-rights-legal-name-error">{LEGAL_NAME_MISMATCH}</p>
        ) : (
          <p className="text-xs text-slate-500">The legal name on your Artist Agreement, not your artist name.</p>
        )}
      </div>

      {!r.owns_everything && (
        <div className="space-y-5">
          {/* Share totals for each side */}
          <div className="space-y-1 border-t border-white/10 pt-4" data-testid="upload-rights-totals">
            <TotalLine label="Writer share" parties={r.writers} />
            <TotalLine label="Publisher share" parties={publishers} />
            <TotalLine label="Master share" parties={r.master_owners} />
          </div>

          {/* Writer + publisher pairs */}
          {r.writers.map((w, i) => {
            const writerSelf = isSelf(w, selfCf);
            return (
              <div
                key={i}
                data-testid={`upload-rights-pair-${i}`}
                className="grid grid-cols-1 gap-4 md:grid-cols-2"
              >
                {/* Writer card */}
                <div className={CARD} data-testid={`upload-rights-writer-${i}`}>
                  <div className="flex items-center justify-between">
                    <h4 className="font-heading text-sm font-semibold text-white">Writer {i + 1}</h4>
                    <button
                      type="button"
                      aria-label={`Remove writer ${i + 1}`}
                      onClick={() => removeWriter(i)}
                      disabled={disabled || r.writers.length < 2}
                      className="flex h-8 w-8 items-center justify-center rounded-md border border-white/10 text-slate-500 transition-colors hover:border-red-400/50 hover:text-white disabled:opacity-30"
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <div className="space-y-1">
                    <span className="text-[11px] text-slate-500">Legal name</span>
                    <Input
                      aria-label={`Writer ${i + 1} legal name`}
                      value={w.legal_name}
                      onChange={(e) => setWriter(i, { legal_name: e.target.value })}
                      maxLength={120}
                      placeholder="Full legal name"
                      disabled={disabled}
                      className={FIELD_CLASS}
                    />
                  </div>
                  <div className="grid grid-cols-[minmax(0,1fr)_96px] gap-2">
                    <div className="space-y-1">
                      <span className="text-[11px] text-slate-500">Role</span>
                      <Select value={w.role} onValueChange={(v) => setWriter(i, { role: v })} disabled={disabled}>
                        <SelectTrigger className="min-w-0 border-white/10 bg-ink text-white focus:ring-electric [&>span]:truncate">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="border-white/10 bg-ink-2 text-white">
                          {WRITER_ROLES.map((o) => (
                            <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <ShareInput label="Share" value={w.pct} onChange={(v) => setWriter(i, { pct: v })} disabled={disabled} />
                  </div>
                  {!writerSelf && (
                    <EmailInput
                      value={w.email}
                      onChange={(v) => setWriter(i, { email: v })}
                      disabled={disabled}
                      testid={`upload-rights-writer-${i}-email`}
                    />
                  )}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <span className="text-[11px] text-slate-500">{requirePro ? 'PRO *' : 'PRO (optional)'}</span>
                      <Select
                        value={w.society || (requirePro ? undefined : NO_PRO)}
                        onValueChange={(v) => setWriter(i, { society: v === NO_PRO ? '' : v })}
                        disabled={disabled}
                      >
                        <SelectTrigger className="border-white/10 bg-ink text-white focus:ring-electric">
                          <SelectValue placeholder="Select PRO" />
                        </SelectTrigger>
                        <SelectContent className="border-white/10 bg-ink-2 text-white">
                          {!requirePro && <SelectItem value={NO_PRO}>None</SelectItem>}
                          {PRO_ORGS.map((o) => (
                            <SelectItem key={o} value={o}>{o}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <span className="text-[11px] text-slate-500">{requirePro ? 'IPI *' : 'IPI (optional)'}</span>
                      <Input
                        aria-label={`Writer ${i + 1} IPI`}
                        inputMode="numeric"
                        maxLength={20}
                        value={w.ipi}
                        onChange={(e) => setWriter(i, { ipi: cleanIpi(e.target.value) })}
                        placeholder={IPI_PLACEHOLDER}
                        disabled={disabled}
                        className={FIELD_CLASS}
                      />
                    </div>
                  </div>
                  {w.society === 'Other' && (
                    <Input aria-label={`Writer ${i + 1} PRO name`} placeholder="Which PRO?" maxLength={80}
                      value={w.society_other || ''} onChange={(e) => setWriter(i, { society_other: e.target.value })}
                      disabled={disabled} className={FIELD_CLASS} />
                  )}
                  {w.ipi && !IPI_PATTERN.test(w.ipi) && (
                    <p className="text-xs text-red-400">{IPI_MESSAGE}</p>
                  )}
                  {requirePro && (!w.society || !w.ipi) && (
                    <p className="text-xs text-amber-300">Sync placements need this writer's PRO and IPI.</p>
                  )}
                </div>

                {/* Publisher card, paired with the writer */}
                <div className={CARD} data-testid={`upload-rights-publisher-${i}`}>
                  <div className="flex items-center justify-between">
                    <h4 className="font-heading text-sm font-semibold text-white">
                      Publisher{w.no_publisher ? '' : `s for writer ${i + 1}`}
                    </h4>
                  </div>
                  <label className="flex cursor-pointer items-start gap-2.5 text-xs text-slate-300">
                    <Checkbox
                      data-testid={`upload-rights-no-publisher-${i}`}
                      checked={w.no_publisher}
                      onCheckedChange={(v) => toggleNoPublisher(i, v === true)}
                      disabled={disabled}
                      className={CHECKBOX_CLASS}
                    />
                    This writer has no publisher on this work
                  </label>

                  {!w.no_publisher && w.publishers.map((p, pi) => {
                    const pubSelf = isSelf(p, selfCf);
                    return (
                      <div key={pi} className="space-y-3 border-t border-white/10 pt-3">
                        <div className="space-y-1">
                          <span className="text-[11px] text-slate-500">Publisher legal name</span>
                          <div className="flex gap-2">
                            <Input
                              aria-label={`Publisher ${pi + 1} for writer ${i + 1} legal name`}
                              value={p.legal_name}
                              onChange={(e) => setPublisher(i, pi, { legal_name: e.target.value })}
                              maxLength={120}
                              placeholder="Full legal name or company"
                              disabled={disabled}
                              className={FIELD_CLASS}
                            />
                            <button
                              type="button"
                              aria-label={`Remove publisher ${pi + 1} for writer ${i + 1}`}
                              onClick={() => removePublisher(i, pi)}
                              disabled={disabled || w.publishers.length < 2}
                              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-white/10 text-slate-500 transition-colors hover:border-red-400/50 hover:text-white disabled:opacity-30"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        </div>
                        <ShareInput label="Share" value={p.pct} onChange={(v) => setPublisher(i, pi, { pct: v })} disabled={disabled} />
                        {!pubSelf && (
                          <EmailInput
                            value={p.email}
                            onChange={(v) => setPublisher(i, pi, { email: v })}
                            disabled={disabled}
                            testid={`upload-rights-publisher-${i}-${pi}-email`}
                          />
                        )}
                      </div>
                    );
                  })}

                  {!w.no_publisher && (
                    <button
                      type="button"
                      className={SMALL_BTN}
                      onClick={() => addPublisher(i)}
                      disabled={disabled || publishers.length >= MAX_PARTIES}
                    >
                      + Add publisher
                    </button>
                  )}
                </div>
              </div>
            );
          })}

          <button
            type="button"
            data-testid="upload-rights-add-writer"
            className={SMALL_BTN}
            onClick={addWriter}
            disabled={disabled || r.writers.length >= MAX_PARTIES}
          >
            + Add writer
          </button>

          {/* Master owners */}
          <div className="space-y-3 border-t border-white/10 pt-4" data-testid="upload-rights-master_owners">
            <h4 className="font-heading text-sm font-semibold text-white">
              Master owners <span className="font-sans text-xs font-normal text-slate-500">(who owns the recording)</span>
            </h4>
            {r.master_owners.map((o, i) => {
              const ownerSelf = isSelf(o, selfCf);
              return (
                <div key={i} className="space-y-3 rounded-xl border border-white/10 p-3">
                  <div className="grid grid-cols-[minmax(0,1fr)_96px_36px] gap-2">
                    <div className="space-y-1">
                      <span className="text-[11px] text-slate-500">Legal name</span>
                      <Input
                        aria-label={`Master owner ${i + 1} legal name`}
                        value={o.legal_name}
                        onChange={(e) => setOwner(i, { legal_name: e.target.value })}
                        maxLength={120}
                        placeholder="Person or label"
                        disabled={disabled}
                        className={FIELD_CLASS}
                      />
                    </div>
                    <ShareInput label="Share" value={o.pct} onChange={(v) => setOwner(i, { pct: v })} disabled={disabled} />
                    <div className="space-y-1">
                      <span className="text-[11px] text-transparent">x</span>
                      <button
                        type="button"
                        aria-label={`Remove master owner ${i + 1}`}
                        onClick={() => removeOwner(i)}
                        disabled={disabled || r.master_owners.length < 2}
                        className="flex h-9 w-9 items-center justify-center rounded-md border border-white/10 text-slate-500 transition-colors hover:border-red-400/50 hover:text-white disabled:opacity-30"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  </div>
                  {!ownerSelf && (
                    <EmailInput
                      value={o.email}
                      onChange={(v) => setOwner(i, { email: v })}
                      disabled={disabled}
                      testid={`upload-rights-master_owners-${i}-email`}
                    />
                  )}
                </div>
              );
            })}
            <button
              type="button"
              className={SMALL_BTN}
              onClick={addOwner}
              disabled={disabled || r.master_owners.length >= MAX_PARTIES}
            >
              + Add owner
            </button>
          </div>

          <p className="text-xs leading-relaxed text-slate-500">
            Everyone you list here, except you, gets an email asking them to sign. Your song can be
            licensed once they all sign.
          </p>
        </div>
      )}

      <label className="flex cursor-pointer items-start gap-3 border-t border-white/10 pt-4 text-sm text-slate-300">
        <Checkbox
          data-testid="upload-rights-attest"
          checked={r.attested}
          onCheckedChange={(v) => set({ attested: v === true })}
          disabled={disabled}
          className={CHECKBOX_CLASS}
        />
        I confirm these splits are accurate and I have the authority to license this recording.
      </label>
    </div>
  );
};

export default RightsSection;
