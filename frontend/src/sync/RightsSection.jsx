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
  IPI_PATTERN,
  MAX_PARTIES,
  PRO_ORGS,
  PUBLISHER_ROLES,
  TOTAL_BP,
  WRITER_ROLES,
} from './constants';

// Splits for every upload. PRD-02 rights model, PRD-03 section 4.1 (check 1).
// Shares are typed as percentages and sent as integer basis points.

const SIDES = [
  { key: 'writers', title: 'Writers', add: 'Add writer', roles: WRITER_ROLES, placeholder: 'Full legal name' },
  { key: 'publishers', title: 'Publishers', add: 'Add publisher', roles: PUBLISHER_ROLES, placeholder: 'Full legal name or company' },
  { key: 'master_owners', title: 'Master owners', add: 'Add owner', roles: null, placeholder: 'Person or label' },
];

const NO_PRO = 'none';

const newParty = (side, legalName = '') => ({
  legal_name: legalName,
  pct: '',
  role: side === 'writers' ? 'CA' : side === 'publishers' ? 'E' : null,
  society: '',
  ipi: '',
});

export const emptyRights = () => ({
  owns_everything: false,
  self_legal_name: '',
  legal_name_touched: false,
  writers: [newParty('writers')],
  publishers: [newParty('publishers')],
  master_owners: [newParty('master_owners')],
  attested: false,
});

export const toBp = (pct) => {
  const n = parseFloat(pct);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
};

const fmtPct = (bp) => (bp / 100).toFixed(2).replace(/\.?0+$/, '');

const sideTotal = (parties) => parties.reduce((sum, p) => sum + toBp(p.pct), 0);

const sideProblem = (parties) => {
  if (parties.length < 1 || parties.length > MAX_PARTIES) return true;
  if (parties.some((p) => !p.legal_name.trim() || toBp(p.pct) < 1)) return true;
  if (parties.some((p) => p.ipi && !IPI_PATTERN.test(p.ipi))) return true;
  const names = parties.map((p) => p.legal_name.trim().toLowerCase());
  if (new Set(names).size !== names.length) return true;
  return sideTotal(parties) !== TOTAL_BP;
};

export const isRightsValid = (r) => {
  if (!r.self_legal_name.trim() || !r.attested) return false;
  if (r.owns_everything) return true;
  return SIDES.every((s) => !sideProblem(r[s.key]));
};

export const buildRightsPayload = (r) => {
  const party = (side) => (p) => ({
    legal_name: p.legal_name.trim(),
    share_bp: toBp(p.pct),
    role: side === 'master_owners' ? null : p.role,
    society: p.society || null,
    ipi_name_number: p.ipi || null,
  });
  return {
    owns_everything: r.owns_everything,
    self_legal_name: r.self_legal_name.trim(),
    writers: r.owns_everything ? [] : r.writers.map(party('writers')),
    publishers: r.owns_everything ? [] : r.publishers.map(party('publishers')),
    master_owners: r.owns_everything ? [] : r.master_owners.map(party('master_owners')),
    attested: r.attested,
  };
};

const CHECKBOX_CLASS =
  'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white focus-visible:ring-electric';
const FIELD_CLASS =
  'border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric';
const SMALL_BTN =
  'rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 transition-colors hover:border-electric/40 hover:text-white disabled:opacity-40';

const RightsSection = ({ value, onChange, disabled }) => {
  const r = value;
  const set = (patch) => onChange({ ...r, ...patch });

  const setParty = (side, i, patch) => {
    const list = r[side].map((p, idx) => (idx === i ? { ...p, ...patch } : p));
    set({ [side]: list });
  };
  const addParty = (side) => {
    if (r[side].length < MAX_PARTIES) set({ [side]: [...r[side], newParty(side)] });
  };
  const removeParty = (side, i) => {
    if (r[side].length > 1) set({ [side]: r[side].filter((_, idx) => idx !== i) });
  };
  const splitEvenly = (side) => {
    const n = r[side].length;
    const base = Math.floor(TOTAL_BP / n);
    const rem = TOTAL_BP - base * n;
    set({ [side]: r[side].map((p, i) => ({ ...p, pct: fmtPct(base + (i === 0 ? rem : 0)) })) });
  };
  const selfPublish = () => {
    set({ publishers: [{ ...newParty('publishers', r.self_legal_name.trim()), pct: '100' }] });
  };

  const cleanPct = (raw) => {
    const s = raw.replace(/[^0-9.]/g, '');
    const [whole, ...rest] = s.split('.');
    return rest.length ? `${whole}.${rest.join('').slice(0, 2)}` : whole;
  };

  return (
    <div className="space-y-4" data-testid="upload-rights">
      <Label className="text-slate-300">Who owns this song? *</Label>

      <label
        htmlFor="rights-own"
        className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3.5 transition-colors ${
          r.owns_everything
            ? 'border-electric/60 bg-electric/[0.06]'
            : 'border-white/10 hover:border-electric/35'
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
        <p className="text-xs text-slate-500">As registered with your PRO, not your artist name.</p>
      </div>

      {!r.owns_everything && (
        <div className="space-y-5">
          {SIDES.map((side) => {
            const parties = r[side.key];
            const total = sideTotal(parties);
            const ok = total === TOTAL_BP;
            const names = parties.map((p) => p.legal_name.trim().toLowerCase()).filter(Boolean);
            const dupes = new Set(names).size !== names.length;
            return (
              <div key={side.key} className="space-y-3 border-t border-white/10 pt-4" data-testid={`upload-rights-${side.key}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="font-heading text-sm font-semibold text-white">
                    {side.title}{' '}
                    <span className="font-sans text-xs font-normal text-slate-500">(1 to 4, must total 100%)</span>
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {side.key === 'publishers' && (
                      <button type="button" className={SMALL_BTN} onClick={selfPublish} disabled={disabled}>
                        I self-publish
                      </button>
                    )}
                    <button type="button" className={SMALL_BTN} onClick={() => splitEvenly(side.key)} disabled={disabled}>
                      Split evenly
                    </button>
                    {parties.length < MAX_PARTIES && (
                      <button type="button" className={SMALL_BTN} onClick={() => addParty(side.key)} disabled={disabled}>
                        + {side.add}
                      </button>
                    )}
                  </div>
                </div>

                {parties.map((p, i) => (
                  <div key={i} className="grid grid-cols-[1fr_96px_36px] gap-2 rounded-xl border border-white/10 p-3">
                    <div className="space-y-1">
                      <span className="text-[11px] text-slate-500">Legal name</span>
                      <Input
                        aria-label={`${side.title} ${i + 1} legal name`}
                        value={p.legal_name}
                        onChange={(e) => setParty(side.key, i, { legal_name: e.target.value })}
                        maxLength={120}
                        placeholder={side.placeholder}
                        disabled={disabled}
                        className={FIELD_CLASS}
                      />
                    </div>
                    <div className="space-y-1">
                      <span className="text-[11px] text-slate-500">Share</span>
                      <div className="relative">
                        <Input
                          aria-label={`${side.title} ${i + 1} share`}
                          inputMode="decimal"
                          value={p.pct}
                          onChange={(e) => setParty(side.key, i, { pct: cleanPct(e.target.value) })}
                          placeholder="0"
                          disabled={disabled}
                          className={`${FIELD_CLASS} pr-6 text-right`}
                        />
                        <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-sm text-slate-500">%</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <span className="text-[11px] text-transparent">x</span>
                      <button
                        type="button"
                        aria-label={`Remove ${side.title.toLowerCase()} ${i + 1}`}
                        onClick={() => removeParty(side.key, i)}
                        disabled={disabled || parties.length < 2}
                        className="flex h-9 w-9 items-center justify-center rounded-md border border-white/10 text-slate-500 transition-colors hover:border-red-400/50 hover:text-white disabled:opacity-30"
                      >
                        <X size={14} />
                      </button>
                    </div>

                    {side.roles && (
                      <div className="col-span-3 grid grid-cols-1 gap-2 sm:grid-cols-[1.5fr_1fr_1fr]">
                        <div className="space-y-1">
                          <span className="text-[11px] text-slate-500">Role (optional)</span>
                          <Select value={p.role} onValueChange={(v) => setParty(side.key, i, { role: v })} disabled={disabled}>
                            <SelectTrigger className="border-white/10 bg-ink text-white focus:ring-electric">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="border-white/10 bg-ink-2 text-white">
                              {side.roles.map((o) => (
                                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[11px] text-slate-500">PRO (optional)</span>
                          <Select
                            value={p.society || NO_PRO}
                            onValueChange={(v) => setParty(side.key, i, { society: v === NO_PRO ? '' : v })}
                            disabled={disabled}
                          >
                            <SelectTrigger className="border-white/10 bg-ink text-white focus:ring-electric">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="border-white/10 bg-ink-2 text-white">
                              <SelectItem value={NO_PRO}>None</SelectItem>
                              {PRO_ORGS.map((o) => (
                                <SelectItem key={o} value={o}>{o}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[11px] text-slate-500">IPI (optional)</span>
                          <Input
                            aria-label={`${side.title} ${i + 1} IPI`}
                            inputMode="numeric"
                            maxLength={11}
                            value={p.ipi}
                            onChange={(e) => setParty(side.key, i, { ipi: e.target.value.replace(/\D/g, '') })}
                            placeholder="9 or 11 digits"
                            disabled={disabled}
                            className={FIELD_CLASS}
                          />
                        </div>
                        {p.ipi && !IPI_PATTERN.test(p.ipi) && (
                          <p className="text-xs text-red-400 sm:col-span-3">IPI must be 9 or 11 digits.</p>
                        )}
                      </div>
                    )}
                  </div>
                ))}

                <p className={`text-xs ${ok ? 'text-green-400' : 'text-red-400'}`} data-testid={`upload-rights-${side.key}-total`}>
                  Total: {fmtPct(total)}%
                  {ok ? ' ✓' : total < TOTAL_BP ? `, ${fmtPct(TOTAL_BP - total)}% left` : `, ${fmtPct(total - TOTAL_BP)}% over`}
                </p>
                {dupes && <p className="text-xs text-red-400">The same name appears twice.</p>}
              </div>
            );
          })}
          <p className="text-xs leading-relaxed text-slate-500">
            Writer and publisher shares are each 100% of their own side. Together they make up the full songwriting royalty.
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
