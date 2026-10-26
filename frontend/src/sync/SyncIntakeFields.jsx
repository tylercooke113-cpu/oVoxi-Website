import React from 'react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { CONTENT_ID_OPTIONS, DISTRIBUTORS, IPI_PATTERN, PRO_ORGS } from './constants';

// The sync questions (PRD-03 4.1; Brief 25b C2), used in the upload form and when adding
// sync from the Vault. Samples moved to DeclarationsFields (asked once, for every use).
// Sync needs a PRO (Agreement 3.5): ticking "not affiliated" calls onNotAffiliated, and the
// caller turns sync off and shows PRO_REQUIRED_MESSAGE.

export const EMPTY_INTAKE = {
  distributor: '', content_id: '', pro_name: '', ipi: '', sync_sole_attested: false,
};

export const isIntakeValid = (i) => !!(i.distributor && i.content_id && i.pro_name
  && IPI_PATTERN.test(i.ipi || '') && i.sync_sole_attested);

export const buildIntakePayload = (i) => ({
  distributor: i.distributor,
  content_id: i.content_id,
  pro_not_affiliated: false,
  pro_name: i.pro_name,
  ipi: i.ipi,
  sync_sole_attested: i.sync_sole_attested,
});

const CHECKBOX = 'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white';
const RADIO = 'mt-0.5 border-white/30 text-electric data-[state=checked]:border-electric [&_svg]:fill-electric';
const FIELD = 'border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric';

const SyncIntakeFields = ({ value, onChange, disabled, onNotAffiliated }) => {
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label className="text-slate-300">Distributor *</Label>
        <Select value={value.distributor} onValueChange={(v) => set({ distributor: v })} disabled={disabled}>
          <SelectTrigger className="border-white/10 bg-ink text-white"><SelectValue placeholder="Select distributor" /></SelectTrigger>
          <SelectContent className="border-white/10 bg-ink-2 text-white">
            {DISTRIBUTORS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label className="text-slate-300">Is this song registered in YouTube Content ID? *</Label>
        <RadioGroup value={value.content_id} onValueChange={(v) => set({ content_id: v })} disabled={disabled}
          className="flex flex-wrap gap-5">
          {CONTENT_ID_OPTIONS.map((o) => (
            <label key={o.value} className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
              <RadioGroupItem value={o.value} className={RADIO} />{o.label}
            </label>
          ))}
        </RadioGroup>
        <p className="text-xs text-slate-500">
          Songs in Content ID are not listed in the OVOXI Catalog, because buyers' videos would be claimed.
        </p>
      </div>

      <div className="space-y-3">
        <Label className="text-slate-300">Performing rights (PRO) *</Label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Select value={value.pro_name} onValueChange={(v) => set({ pro_name: v })} disabled={disabled}>
            <SelectTrigger aria-label="PRO" className="border-white/10 bg-ink text-white"><SelectValue placeholder="Select PRO" /></SelectTrigger>
            <SelectContent className="border-white/10 bg-ink-2 text-white">
              {PRO_ORGS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
            </SelectContent>
          </Select>
          <div>
            <Input aria-label="IPI number" inputMode="numeric" maxLength={11} value={value.ipi} placeholder="IPI: 9 or 11 digits"
              onChange={(e) => set({ ipi: e.target.value.replace(/\D/g, '') })} disabled={disabled} className={FIELD} />
            {value.ipi && !IPI_PATTERN.test(value.ipi) && (
              <p className="mt-1 text-xs text-red-400">IPI must be 9 or 11 digits.</p>
            )}
          </div>
        </div>
        <p className="text-xs text-slate-500">Your IPI number is in your PRO account. Every writer in the splits needs one too.</p>
        {onNotAffiliated && (
          <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
            <Checkbox checked={false} onCheckedChange={(v) => v === true && onNotAffiliated()}
              disabled={disabled} className={CHECKBOX} data-testid="sync-not-affiliated" />
            I'm not affiliated with a PRO.
          </label>
        )}
      </div>

      <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
        <Checkbox checked={value.sync_sole_attested} data-testid="sync-sole-attested"
          onCheckedChange={(v) => set({ sync_sole_attested: v === true })} disabled={disabled} className={CHECKBOX} />
        This song is not offered for sync anywhere else, including another music library, a distributor's sync
        program or a publisher.
      </label>
    </div>
  );
};

export default SyncIntakeFields;
