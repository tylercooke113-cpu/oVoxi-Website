import React, { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Upload, Music2 } from 'lucide-react';
import { openAgreementPdf, formatSignedDate } from '../agreement/agreementApi';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import {
  MOODS,
  MAX_MOODS,
  VOCALS_OPTIONS,
  BPM_MIN,
  BPM_MAX,
  MAJOR_KEYS,
  MINOR_KEYS,
  LOOPS_NO_AI_MESSAGE,
} from '../sync/constants';
import RightsSection, {
  emptyRights, isRightsValid, legalNameMismatch, rightsEmails, writersMissingPro,
} from '../sync/RightsSection';
import SyncIntakeFields, { EMPTY_INTAKE, isIntakeValid, buildIntakePayload } from '../sync/SyncIntakeFields';
import DeclarationsFields from './DeclarationsFields';
import { EMPTY_DECLARATIONS, declarationsMissing, usesLoops } from './declarations';

export const GENRES = [
  'Hip-Hop', 'R&B', 'Afrobeats', 'Trap', 'Soul',
  'Pop', 'Electronic', 'Latin', 'Reggaeton', 'Afropop', 'Other',
];

export const MAX_BYTES = 150 * 1024 * 1024; // 150 MB, matches MAX_UPLOAD_BYTES on Railway
export const MAX_SONGS = 15;

// One copy of the sync questions and rules (Brief 25b C2), shared with the Vault.
export { EMPTY_INTAKE, isIntakeValid, buildIntakePayload };

let _songSeq = 0;

// One song in the batch. `key` is stable for React and status tracking.
export const emptySong = (overrides = {}) => ({
  key: `song-${++_songSeq}`,
  form: { artist_name: '', track_name: '', genre: '', genre_other: '' },
  file: null,
  moods: [],
  vocals: '',
  bpm: '',
  bpmUnsure: false,
  musicalKey: '',
  keyUnsure: false,
  consentAi: false,
  consentSync: false,
  consentExclusive: false,       // always non-exclusive at upload; Exclusive is a Vault switch (Oct 26)
  declarations: EMPTY_DECLARATIONS,
  proNotice: false,              // "not affiliated" is ticked: sync is off, the PRO box explains why
  intake: EMPTY_INTAKE,
  rights: emptyRights(),
  status: 'draft', // draft | queued | uploading | received | failed
  progress: 0,
  submissionId: null,
  error: null,
  ...overrides,
});

// A new song seeded from the one before it. Only the fields in brief A3 carry over;
// everything else starts empty.
export const carryOverSong = (prev) => emptySong({
  form: { artist_name: prev.form.artist_name, track_name: '', genre: '', genre_other: '' },
  consentAi: prev.consentAi,
  consentSync: prev.consentSync,
  intake: {
    ...EMPTY_INTAKE,
    distributor: prev.intake.distributor,
    distributor_other: prev.intake.distributor_other || '',
    pro_name: prev.intake.pro_name,
    ipi: prev.intake.ipi,
  },
  rights: {
    ...emptyRights(),
    self_legal_name: prev.rights.self_legal_name,
    legal_name_touched: prev.rights.legal_name_touched,
    account_legal_name: prev.rights.account_legal_name,
  },
});

// Anything the artist has typed or chosen, so Remove knows whether to confirm first.
export const songHasData = (song) => {
  const { form, file, moods, vocals, bpm, musicalKey, consentAi, consentSync, rights } = song;
  return !!(
    file || form.artist_name || form.track_name || form.genre ||
    moods.length || vocals || bpm || musicalKey ||
    consentAi || consentSync ||
    rights.self_legal_name || rights.legal_name_touched
  );
};

// Pure validation, identical to the single-song rules it replaces. Exported for tests.
export const songMissing = (song) => {
  const {
    form, moods, vocals, bpm, bpmUnsure, musicalKey, keyUnsure,
    consentAi, consentSync, intake, rights, file, declarations,
  } = song;
  const missing = [];
  if (!form.artist_name) missing.push('artist name');
  if (!form.track_name) missing.push('track name');
  if (!form.genre) missing.push('genre');
  else if (form.genre === 'Other' && !(form.genre_other || '').trim()) missing.push('which genre');
  if (moods.length < 1) missing.push('mood');
  if (!vocals) missing.push('vocals');
  const bpmNumber = parseFloat(bpm);
  const bpmValid = Number.isFinite(bpmNumber) && bpmNumber >= BPM_MIN && bpmNumber <= BPM_MAX;
  if (!bpmUnsure && !bpmValid) missing.push('BPM');
  if (!keyUnsure && !musicalKey) missing.push('key');
  if (!consentAi && !consentSync) missing.push('how it can be used');
  if (consentAi && usesLoops(declarations)) missing.push('AI training off (songs with loops are sync only)');
  missing.push(...declarationsMissing(declarations, { rightsEmails: rightsEmails(rights), requireFiles: true }));
  if (legalNameMismatch(rights)) missing.push('your legal name as on your account');
  else if (!isRightsValid(rights, { requirePro: consentSync })) {
    missing.push(consentSync && writersMissingPro(rights).length ? "every writer's PRO and IPI" : 'splits');
  }
  if (consentSync && !isIntakeValid(intake)) missing.push('sync details');
  if (!file) missing.push('audio file');
  return missing;
};

const CHECKBOX_CLASS =
  'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white focus-visible:ring-electric';

// Controlled single-song form. `value` is a song object; `onChange` merges a partial
// into it. `index` keeps data-testids and ids unique across the batch.
const SongForm = ({ value, onChange, index, disabled, agreementStatus, getToken }) => {
  const fileRef = useRef(null);
  const [moodLimitHit, setMoodLimitHit] = useState(false);

  const tid = (base) => `${base}-${index}`;
  const patch = onChange;

  const bpmNumber = parseFloat(value.bpm);
  const bpmValid = Number.isFinite(bpmNumber) && bpmNumber >= BPM_MIN && bpmNumber <= BPM_MAX;

  const update = (key) => (e) => {
    const v = e.target.value;
    patch({ form: { ...value.form, [key]: v } });
  };


  const toggleMood = (m) => {
    if (value.moods.includes(m)) {
      patch({ moods: value.moods.filter((x) => x !== m) });
      setMoodLimitHit(false);
    } else if (value.moods.length >= MAX_MOODS) {
      setMoodLimitHit(true);
    } else {
      patch({ moods: [...value.moods, m] });
    }
  };

  // Oct 26: prefill the legal name from the signed Artist Agreement (not the artist name),
  // and keep the account name on the splits so a different name is flagged.
  const accountName = agreementStatus?.legal_name || '';
  useEffect(() => {
    if (!accountName || value.rights.account_legal_name === accountName) return;
    patch({ rights: {
      ...value.rights,
      account_legal_name: accountName,
      self_legal_name: value.rights.legal_name_touched && value.rights.self_legal_name
        ? value.rights.self_legal_name : accountName,
    } });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountName, value.rights.account_legal_name]);

  const toggleSync = (checked) => {
    patch({ consentSync: checked, proNotice: false, intake: checked ? value.intake : EMPTY_INTAKE });
  };

  // Agreement 3.5: "not affiliated with a PRO" means AI training only. Ticking it unchecks
  // sync but keeps the PRO box open with the reason; unticking turns sync back on.
  const notAffiliated = (checked) => (checked
    ? patch({ consentSync: false, intake: EMPTY_INTAKE, proNotice: true })
    : patch({ consentSync: true, proNotice: false }));

  // Agreement 3.6: songs with loops are sync only.
  const setDeclarations = (d) => patch(usesLoops(d)
    ? { declarations: d, consentAi: false }
    : { declarations: d });
  const loopSong = usesLoops(value.declarations);

  const handleFile = (f) => {
    if (!f) return;
    if (f.size > MAX_BYTES) {
      toast.error('File exceeds the 150 MB limit.');
      return;
    }
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['mp3', 'wav'].includes(ext)) {
      toast.error('Only MP3 or WAV files are accepted.');
      return;
    }
    patch({ file: f });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files && files.length > 1) {
      toast('Add one song at a time. Use + for the next one.');
    }
    handleFile(files?.[0]);
  };

  const file = value.file;

  return (
    <div
      data-testid={tid('upload-form')}
      className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 md:p-10 space-y-6"
    >
      {/* Artist + Track Name */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={tid('upload-artist')} className="text-slate-300">
            Artist Name *
          </Label>
          <Input
            id={tid('upload-artist')}
            data-testid={tid('upload-artist-input')}
            value={value.form.artist_name}
            onChange={update('artist_name')}
            placeholder="Your stage name"
            disabled={disabled}
            className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={tid('upload-track')} className="text-slate-300">
            Track Name *
          </Label>
          <Input
            id={tid('upload-track')}
            data-testid={tid('upload-track-input')}
            value={value.form.track_name}
            onChange={update('track_name')}
            placeholder="Song title"
            disabled={disabled}
            className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
          />
        </div>
      </div>

      {/* Genre */}
      <div className="space-y-2">
        <Label className="text-slate-300">Genre *</Label>
        <Select
          value={value.form.genre}
          onValueChange={(v) => patch({ form: { ...value.form, genre: v, ...(v !== 'Other' ? { genre_other: '' } : {}) } })}
          disabled={disabled}
        >
          <SelectTrigger
            data-testid={tid('upload-genre-select')}
            className="border-white/10 bg-ink text-white focus:ring-electric"
          >
            <SelectValue placeholder="Select genre" />
          </SelectTrigger>
          <SelectContent className="border-white/10 bg-ink-2 text-white">
            {GENRES.map((g) => (
              <SelectItem key={g} value={g}>{g}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {value.form.genre === 'Other' && (
          <Input
            aria-label="Which genre?"
            placeholder="Which genre? *"
            maxLength={80}
            value={value.form.genre_other || ''}
            onChange={(e) => patch({ form: { ...value.form, genre_other: e.target.value } })}
            disabled={disabled}
            data-testid={tid('upload-genre-other')}
            className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
          />
        )}
      </div>

      {/* Moods */}
      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <Label className="text-slate-300">
            Mood * <span className="text-slate-500">(pick 1 to 3)</span>
          </Label>
          <span className="text-xs text-slate-500">{value.moods.length} / {MAX_MOODS}</span>
        </div>
        <div className="flex flex-wrap gap-2" data-testid={tid('upload-moods')}>
          {MOODS.map((m) => {
            const on = value.moods.includes(m);
            return (
              <button
                key={m}
                type="button"
                aria-pressed={on}
                onClick={() => toggleMood(m)}
                disabled={disabled}
                className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
                  on
                    ? 'border-electric-light bg-electric/20 text-white'
                    : 'border-white/10 text-slate-300 hover:border-electric/40 hover:text-white'
                }`}
              >
                {m}
              </button>
            );
          })}
        </div>
        {moodLimitHit && (
          <p className="text-xs text-red-400">Up to 3 moods.</p>
        )}
      </div>

      {/* Vocals */}
      <div className="space-y-2">
        <Label className="text-slate-300">Vocals *</Label>
        <div className="flex" data-testid={tid('upload-vocals')}>
          <div className="inline-flex rounded-full border border-white/10 p-1">
            {VOCALS_OPTIONS.map((o) => (
              <button
                key={o.value}
                type="button"
                aria-pressed={value.vocals === o.value}
                onClick={() => patch({ vocals: o.value })}
                disabled={disabled}
                className={`rounded-full px-5 py-1.5 text-sm transition-colors ${
                  value.vocals === o.value
                    ? 'bg-gradient-brand text-white'
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* BPM and key: the artist's answer is the source of truth (PRD-03 4.4) */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={tid('upload-bpm')} className="text-slate-300">BPM *</Label>
          <Input
            id={tid('upload-bpm')}
            data-testid={tid('upload-bpm-input')}
            inputMode="decimal"
            value={value.bpm}
            onChange={(e) => {
              const v = e.target.value.replace(/[^0-9.]/g, '');
              const [whole, ...rest] = v.split('.');
              patch({ bpm: rest.length ? `${whole.slice(0, 3)}.${rest.join('').slice(0, 1)}` : whole.slice(0, 3) });
            }}
            placeholder="e.g. 128"
            disabled={disabled || value.bpmUnsure}
            className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
          />
          {!value.bpmUnsure && value.bpm && !bpmValid && (
            <p className="text-xs text-red-400">BPM must be between {BPM_MIN} and {BPM_MAX}.</p>
          )}
          <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
            <Checkbox
              data-testid={tid('upload-bpm-unsure')}
              checked={value.bpmUnsure}
              onCheckedChange={(v) => patch({ bpmUnsure: v === true, ...(v === true ? { bpm: '' } : {}) })}
              disabled={disabled}
              className={CHECKBOX_CLASS}
            />
            I'm unsure
          </label>
        </div>
        <div className="space-y-2">
          <Label className="text-slate-300">Key *</Label>
          <Select
            value={value.musicalKey}
            onValueChange={(v) => patch({ musicalKey: v })}
            disabled={disabled || value.keyUnsure}
          >
            <SelectTrigger
              data-testid={tid('upload-key-select')}
              className="border-white/10 bg-ink text-white focus:ring-electric"
            >
              <SelectValue placeholder="Select key" />
            </SelectTrigger>
            <SelectContent className="max-h-72 border-white/10 bg-ink-2 text-white">
              {[...MAJOR_KEYS, ...MINOR_KEYS].map((k) => (
                <SelectItem key={k} value={k}>{k}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
            <Checkbox
              data-testid={tid('upload-key-unsure')}
              checked={value.keyUnsure}
              onCheckedChange={(v) => patch({ keyUnsure: v === true, ...(v === true ? { musicalKey: '' } : {}) })}
              disabled={disabled}
              className={CHECKBOX_CLASS}
            />
            I'm unsure
          </label>
        </div>
      </div>
      <p className="-mt-3 text-xs text-slate-500">
        Use the tempo and key from your session. We double-check them after processing.
      </p>

      <div className="border-t border-white/10" />

      {/* Consent (Brief 25b C1: sync first, then AI training). Exclusive is a Vault switch. */}
      <div className="space-y-3">
        <Label className="text-slate-300">How can this upload be used? *</Label>
        {[
          {
            id: tid('consent-sync'),
            testid: tid('upload-consent-sync'),
            checked: value.consentSync,
            onChange: toggleSync,
            title: 'Use this upload for sync placements.',
            help: 'Listed in the OVOXI Catalog for creators and brands to license.',
          },
          {
            id: tid('consent-ai'),
            testid: tid('upload-consent-ai'),
            checked: value.consentAi,
            onChange: (v) => patch({ consentAi: v }),
            title: 'Use this upload for AI training.',
            help: loopSong ? LOOPS_NO_AI_MESSAGE : 'Licensed to AI companies as training data.',
            blocked: loopSong,
          },
        ].map((c) => (
          <label
            key={c.id}
            htmlFor={c.id}
            className={`flex items-start gap-3 rounded-xl border px-4 py-3.5 transition-colors ${
              c.blocked ? 'cursor-not-allowed border-white/10 opacity-60'
                : c.checked ? 'cursor-pointer border-electric/60 bg-electric/[0.06]'
                : 'cursor-pointer border-white/10 hover:border-electric/35'
            }`}
          >
            <Checkbox
              id={c.id}
              data-testid={c.testid}
              checked={c.checked}
              onCheckedChange={(v) => c.onChange(v === true)}
              disabled={disabled || c.blocked}
              className={CHECKBOX_CLASS}
            />
            <span>
              <span className="block text-sm font-medium text-white">{c.title}</span>
              <span className="mt-0.5 block text-xs text-slate-500">{c.help}</span>
            </span>
          </label>
        ))}
        {!value.consentAi && !value.consentSync && (
          <p className="text-xs text-red-400">Choose at least one.</p>
        )}
        {agreementStatus?.signed && agreementStatus.agreement && (
          <div className="mt-2.5 border-t border-white/10 pt-2.5 text-xs text-slate-500">
            These uses are licensed under your Artist Agreement signed{' '}
            {formatSignedDate(agreementStatus.agreement.signed_at)}.{' '}
            <button type="button" onClick={() => openAgreementPdf(getToken)} className="text-cyan hover:underline">
              View agreement
            </button>
          </div>
        )}
      </div>

      {/* Samples, loops and AI tools (every upload; Brief 25b D1, F) */}
      <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.01] p-5 sm:p-6">
        <h3 className="font-heading text-base font-semibold text-white">About this song</h3>
        <DeclarationsFields value={value.declarations} onChange={setDeclarations} disabled={disabled}
          idPrefix={tid('upload-decl')} withFiles />
      </div>

      {/* Splits (every upload). With sync on, every writer needs a PRO and IPI. */}
      <RightsSection value={value.rights} onChange={(r) => patch({ rights: r })} disabled={disabled}
        requirePro={value.consentSync} />

      {/* Sync details (stays open, PRO box only, while "not affiliated" is ticked) */}
      {(value.consentSync || value.proNotice) && (
        <div
          data-testid={tid('upload-sync-panel')}
          className="space-y-6 rounded-2xl border border-cyan/25 bg-cyan/[0.03] p-5 sm:p-6"
        >
          <div>
            <h3 className="font-heading text-base font-semibold text-white">Sync details</h3>
            <p className="mt-1 text-sm text-slate-400">
              Buyers need these answers before your track can be licensed.
            </p>
          </div>
          <SyncIntakeFields value={value.intake} onChange={(i) => patch({ intake: i })}
            disabled={disabled} onNotAffiliated={notAffiliated} notAffiliated={value.proNotice} />
        </div>
      )}

      {/* File drop zone */}
      <div className="space-y-2">
        <Label className="text-slate-300">
          Audio File *{' '}
          <span className="text-slate-500">(MP3 or WAV, max 150 MB)</span>
        </Label>
        <div
          data-testid={tid('upload-dropzone')}
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => !disabled && fileRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-10 text-center transition-colors ${
            file
              ? 'border-electric/50 bg-electric/[0.05]'
              : 'border-white/20 bg-ink/60 hover:border-electric/40 hover:bg-electric/[0.04]'
          } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
        >
          {file ? (
            <Music2 size={28} className="text-electric" />
          ) : (
            <Upload size={28} className="text-slate-500" />
          )}
          {file ? (
            <div>
              <p className="text-sm font-medium text-white">{file.name}</p>
              <p className="text-xs text-slate-500 mt-1">
                {(file.size / (1024 * 1024)).toFixed(1)} MB
              </p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-slate-300">
                Drop your file here or{' '}
                <span className="text-electric">browse</span>
              </p>
              <p className="text-xs text-slate-600 mt-1">
                MP3 or WAV up to 150 MB
              </p>
            </div>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".mp3,.wav,audio/mpeg,audio/wav"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
            disabled={disabled}
          />
        </div>
      </div>
    </div>
  );
};

export default SongForm;
