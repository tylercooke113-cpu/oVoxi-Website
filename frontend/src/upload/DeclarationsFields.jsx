import React from 'react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  AI_TOOLS_DETAIL_MAX, AI_TOOLS_FULL_MESSAGE, AI_TOOLS_OPTIONS, LOOP_SOURCES, LOOPS_NO_AI_MESSAGE,
  MAX_LOOPS, SAMPLE_OPTIONS, SAMPLES_NOT_ALLOWED_MESSAGE,
} from '../sync/constants';
import { emptyLoop, licenseFileProblem, usesLoops } from './declarations';

const CHECKBOX = 'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white focus-visible:ring-electric';
const RADIO = 'mt-0.5 border-white/30 text-electric data-[state=checked]:border-electric focus-visible:ring-electric [&_svg]:fill-electric';
const FIELD = 'border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric';
const SMALL_BTN = 'rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 transition-colors hover:border-electric/40 hover:text-white disabled:opacity-40';

// Samples, loops and AI tools (Brief 25b D1, F). `withFiles` adds a license picker per
// loop (the upload form); the Vault uploads licenses from the track panel instead.
const DeclarationsFields = ({ value, onChange, disabled, idPrefix = 'decl', withFiles = false }) => {
  const set = (patch) => onChange({ ...value, ...patch });
  const setLoop = (i, patch) => set({ loops: value.loops.map((lp, j) => (j === i ? { ...lp, ...patch } : lp)) });
  const tid = (b) => `${idPrefix}-${b}`;

  const chooseSamples = (v) => set({
    samples: v,
    samples_attested: false,
    loops: v === 'royalty_free_loop' ? (value.loops.length ? value.loops : [emptyLoop()]) : [],
  });

  return (
    <div className="space-y-6" data-testid={tid('declarations')}>
      {/* Samples and loops */}
      <div className="space-y-2.5">
        <Label className="text-slate-300">Does this song use samples or loops? *</Label>
        <RadioGroup value={value.samples} onValueChange={chooseSamples} disabled={disabled} className="gap-2.5">
          {SAMPLE_OPTIONS.map((o) => (
            <label key={o.value} className="flex cursor-pointer items-start gap-3 text-sm text-slate-300"
              data-testid={tid(`samples-${o.value}`)}>
              <RadioGroupItem value={o.value} className={RADIO} />{o.label}
            </label>
          ))}
        </RadioGroup>

        {value.samples === 'sample' && (
          <p className="rounded-lg border border-red-400/40 bg-red-400/[0.06] p-3 text-sm text-red-200"
            data-testid={tid('samples-blocked')}>{SAMPLES_NOT_ALLOWED_MESSAGE}</p>
        )}

        {(value.samples === 'original' || usesLoops(value)) && (
          <label className="flex cursor-pointer items-start gap-3 pt-1 text-sm text-slate-300">
            <Checkbox checked={value.samples_attested} data-testid={tid('samples-attested')}
              onCheckedChange={(v) => set({ samples_attested: v === true })} disabled={disabled} className={CHECKBOX} />
            {value.samples === 'original'
              ? 'I confirm no samples of other songs or recordings were used.'
              : "I confirm no samples of other songs or recordings were used, and the only sounds I didn't make are the loops listed below."}
          </label>
        )}

        {usesLoops(value) && (
          <div className="space-y-3 rounded-xl border border-white/10 bg-ink p-4" data-testid={tid('loops')}>
            <p className="text-xs leading-relaxed text-slate-400">
              {LOOPS_NO_AI_MESSAGE} Add each loop creator to the splits below with the same email, with their
              writing, publishing and master shares. We'll email them the Co-owner Consent. Your song stays in
              "Needs docs" until every creator signs and we approve each loop license.
            </p>
            {value.loops.map((lp, i) => {
              const fileProblem = licenseFileProblem(lp.file);
              return (
                <div key={i} className="space-y-2 rounded-lg border border-white/10 p-3" data-testid={tid(`loop-${i}`)}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-white">Loop {i + 1}</span>
                    {value.loops.length > 1 && (
                      <button type="button" className={SMALL_BTN} disabled={disabled}
                        onClick={() => set({ loops: value.loops.filter((_, j) => j !== i) })}>Remove</button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <Input aria-label={`Loop ${i + 1} creator name`} placeholder="Loop creator's legal name"
                      value={lp.creator_name} onChange={(e) => setLoop(i, { creator_name: e.target.value })}
                      disabled={disabled} className={FIELD} />
                    <Input aria-label={`Loop ${i + 1} creator email`} placeholder="Loop creator's email" type="email"
                      value={lp.creator_email} onChange={(e) => setLoop(i, { creator_email: e.target.value })}
                      disabled={disabled} className={FIELD} />
                    <Input aria-label={`Loop ${i + 1} name`} placeholder="Loop or pack name"
                      value={lp.loop_name} onChange={(e) => setLoop(i, { loop_name: e.target.value })}
                      disabled={disabled} className={FIELD} />
                    <Select value={lp.source} onValueChange={(v) => setLoop(i, { source: v })} disabled={disabled}>
                      <SelectTrigger aria-label={`Loop ${i + 1} source`} className="border-white/10 bg-ink text-white">
                        <SelectValue placeholder="Where did you get it?" />
                      </SelectTrigger>
                      <SelectContent className="border-white/10 bg-ink-2 text-white">
                        {LOOP_SOURCES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  {withFiles && (
                    <div className="space-y-1">
                      <span className="text-[11px] text-slate-500">License for this loop * (PDF, PNG or JPG, up to 10 MB)</span>
                      <input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                        aria-label={`Loop ${i + 1} license`} disabled={disabled}
                        onChange={(e) => setLoop(i, { file: e.target.files?.[0] || null })}
                        className="block w-full text-xs text-slate-400 file:mr-3 file:rounded-full file:border-0 file:bg-white/10 file:px-3 file:py-1 file:text-xs file:text-white" />
                      {fileProblem && <p className="text-xs text-red-400">{fileProblem}</p>}
                    </div>
                  )}
                </div>
              );
            })}
            {value.loops.length < MAX_LOOPS && (
              <button type="button" className={SMALL_BTN} disabled={disabled}
                onClick={() => set({ loops: [...value.loops, emptyLoop()] })}>+ Add another loop</button>
            )}
          </div>
        )}
      </div>

      {/* AI tools */}
      <div className="space-y-2.5">
        <Label className="text-slate-300">Did you use AI tools to make this song? *</Label>
        <RadioGroup value={value.ai_tools} onValueChange={(v) => set({ ai_tools: v, ai_tools_attested: false })}
          disabled={disabled} className="gap-2.5">
          {AI_TOOLS_OPTIONS.map((o) => (
            <label key={o.value} className="flex cursor-pointer items-start gap-3 text-sm text-slate-300"
              data-testid={tid(`ai-tools-${o.value}`)}>
              <RadioGroupItem value={o.value} className={RADIO} />
              <span><b className="font-medium text-white">{o.title}</b>{o.help ? ` ${o.help}` : ''}</span>
            </label>
          ))}
        </RadioGroup>
        {value.ai_tools === 'partial' && (
          <div className="space-y-1">
            <Input aria-label="Which parts, and which tool?" placeholder="Which parts, and which tool?"
              maxLength={AI_TOOLS_DETAIL_MAX} value={value.ai_tools_detail}
              onChange={(e) => set({ ai_tools_detail: e.target.value })} disabled={disabled} className={FIELD} />
            <p className="text-xs text-slate-500">We review songs with AI-generated parts before they are listed.</p>
          </div>
        )}
        {value.ai_tools === 'full' && (
          <p className="rounded-lg border border-red-400/40 bg-red-400/[0.06] p-3 text-sm text-red-200"
            data-testid={tid('ai-tools-blocked')}>{AI_TOOLS_FULL_MESSAGE}</p>
        )}
        {value.ai_tools && value.ai_tools !== 'full' && (
          <label className="flex cursor-pointer items-start gap-3 pt-1 text-sm text-slate-300">
            <Checkbox checked={value.ai_tools_attested} data-testid={tid('ai-tools-attested')}
              onCheckedChange={(v) => set({ ai_tools_attested: v === true })} disabled={disabled} className={CHECKBOX} />
            I confirm this answer is accurate. OVOXI and its buyers rely on it.
          </label>
        )}
      </div>
    </div>
  );
};

export default DeclarationsFields;
