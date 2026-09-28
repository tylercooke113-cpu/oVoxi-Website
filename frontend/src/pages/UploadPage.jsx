import React, { useState, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Upload, CheckCircle2, Music2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
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
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import {
  MOODS,
  MAX_MOODS,
  VOCALS_OPTIONS,
  SAMPLE_OPTIONS,
  CONTENT_ID_OPTIONS,
  DISTRIBUTORS,
  PRO_ORGS,
  IPI_PATTERN,
  BPM_MIN,
  BPM_MAX,
  MAJOR_KEYS,
  MINOR_KEYS,
} from '../sync/constants';
import RightsSection, { emptyRights, isRightsValid, buildRightsPayload } from '../sync/RightsSection';

const API = `https://ovoxi-website-production.up.railway.app/api`;

const GENRES = [
  'Hip-Hop', 'R&B', 'Afrobeats', 'Trap', 'Soul',
  'Pop', 'Electronic', 'Latin', 'Reggaeton', 'Afropop', 'Other',
];

const MAX_BYTES = 150 * 1024 * 1024; // 150 MB — matches MAX_UPLOAD_BYTES on Railway

const STATUS_LABELS = {
  pending: 'Queued',
  uploaded: 'Uploaded',
  processing: 'Processing stems…',
  completed: 'Stems ready',
  failed: 'Processing failed',
};

const EMPTY_INTAKE = {
  samples: '',
  samples_attested: false,
  distributor: '',
  content_id: '',
  pro_not_affiliated: false,
  pro_name: '',
  ipi: '',
};

const isIntakeValid = (i) => {
  if (!i.samples || !i.samples_attested || !i.distributor || !i.content_id) return false;
  if (i.pro_not_affiliated) return true;
  return !!i.pro_name && IPI_PATTERN.test(i.ipi);
};

const buildIntakePayload = (i) => ({
  samples: i.samples,
  samples_attested: i.samples_attested,
  distributor: i.distributor,
  content_id: i.content_id,
  pro_not_affiliated: i.pro_not_affiliated,
  pro_name: i.pro_not_affiliated ? null : i.pro_name,
  ipi: i.pro_not_affiliated ? null : i.ipi,
});

// FastAPI returns validation errors as an array; pydantic prefixes
// messages raised in validators with "Value error, ".
const validationMessage = (detail) => {
  const raw = Array.isArray(detail) ? detail[0]?.msg : detail;
  if (!raw || typeof raw !== 'string') return null;
  return raw.replace(/^Value error, /, '');
};

const CHECKBOX_CLASS =
  'mt-0.5 rounded-[3px] border-white/30 data-[state=checked]:border-electric data-[state=checked]:bg-electric data-[state=checked]:text-white focus-visible:ring-electric';
const RADIO_CLASS =
  'mt-0.5 border-white/30 text-electric data-[state=checked]:border-electric focus-visible:ring-electric [&_svg]:fill-electric';

const UploadPage = () => {
  const fileRef = useRef(null);
  const { getToken, isSignedIn, isLoaded } = useAuth();

  const [form, setForm] = useState({ artist_name: '', track_name: '', genre: '' });
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [stage, setStage] = useState('idle'); // idle | uploading | processing | done | error
  const [submissionId, setSubmissionId] = useState(null);
  const [moods, setMoods] = useState([]);
  const [moodLimitHit, setMoodLimitHit] = useState(false);
  const [vocals, setVocals] = useState('');
  const [bpm, setBpm] = useState('');
  const [bpmUnsure, setBpmUnsure] = useState(false);
  const [musicalKey, setMusicalKey] = useState('');
  const [keyUnsure, setKeyUnsure] = useState(false);
  const [consentAi, setConsentAi] = useState(false);
  const [consentSync, setConsentSync] = useState(false);
  const [intake, setIntake] = useState(EMPTY_INTAKE);
  const [rights, setRights] = useState(emptyRights);

  if (isLoaded && !isSignedIn) return <Navigate to='/login' replace />;

  const update = (key) => (e) => {
    const { value } = e.target;
    setForm((f) => ({ ...f, [key]: value }));
    // Prefill the legal name from the artist name until the artist edits it (PRD-02 10.1).
    if (key === 'artist_name') {
      setRights((r) => (r.legal_name_touched ? r : { ...r, self_legal_name: value }));
    }
  };
  const setIntakeField = (key, value) => setIntake((i) => ({ ...i, [key]: value }));

  const toggleMood = (m) => {
    if (moods.includes(m)) {
      setMoods(moods.filter((x) => x !== m));
      setMoodLimitHit(false);
    } else if (moods.length >= MAX_MOODS) {
      setMoodLimitHit(true);
    } else {
      setMoods([...moods, m]);
    }
  };

  const toggleSync = (checked) => {
    setConsentSync(checked);
    if (!checked) setIntake(EMPTY_INTAKE);
  };

  const toggleNotAffiliated = (checked) => {
    setIntake((i) => ({ ...i, pro_not_affiliated: checked, pro_name: '', ipi: '' }));
  };

  const resetForm = () => {
    setStage('idle');
    setFile(null);
    setForm({ artist_name: '', track_name: '', genre: '' });
    setSubmissionId(null);
    setUploadProgress(0);
    setMoods([]);
    setMoodLimitHit(false);
    setVocals('');
    setBpm('');
    setBpmUnsure(false);
    setMusicalKey('');
    setKeyUnsure(false);
    setConsentAi(false);
    setConsentSync(false);
    setIntake(EMPTY_INTAKE);
    setRights(emptyRights());
  };

  const missing = [];
  if (!form.artist_name) missing.push('artist name');
  if (!form.track_name) missing.push('track name');
  if (!form.genre) missing.push('genre');
  if (moods.length < 1) missing.push('mood');
  if (!vocals) missing.push('vocals');
  const bpmNumber = parseFloat(bpm);
  const bpmValid = Number.isFinite(bpmNumber) && bpmNumber >= BPM_MIN && bpmNumber <= BPM_MAX;
  if (!bpmUnsure && !bpmValid) missing.push('BPM');
  if (!keyUnsure && !musicalKey) missing.push('key');
  if (!consentAi && !consentSync) missing.push('how it can be used');
  if (!isRightsValid(rights)) missing.push('splits');
  if (consentSync && !isIntakeValid(intake)) missing.push('sync details');
  if (!file) missing.push('audio file');
  const canSubmit = missing.length === 0;

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
    setFile(f);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    handleFile(e.dataTransfer.files?.[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.artist_name || !form.track_name || !form.genre) {
      toast.error('Please fill in all fields.');
      return;
    }
    if (!file) {
      toast.error('Please select an audio file.');
      return;
    }
    if (!canSubmit) {
      toast.error(`Still needed: ${missing.join(', ')}.`);
      return;
    }

    setStage('uploading');
    setUploadProgress(0);

    try {
      // Step 1: get presigned URL
      const token = await getToken();
      const { data: presignData } = await axios.post(`${API}/upload/presign`, {
        artist_name: form.artist_name,
        track_name: form.track_name,
        genre: form.genre,
        filename: file.name,
        file_size: file.size,
        consent_ai_training: consentAi,
        consent_sync: consentSync,
        moods,
        vocals,
        ...(bpmUnsure ? { bpm_unsure: true } : { bpm: Math.round(bpmNumber * 10) / 10 }),
        ...(keyUnsure ? { key_unsure: true } : { key: musicalKey }),
        rights: buildRightsPayload(rights),
        ...(consentSync ? { sync_intake: buildIntakePayload(intake) } : {}),
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const { presigned_url, submission_id, content_type } = presignData;
      setSubmissionId(submission_id);

      // Step 2: PUT file directly to R2
      await axios.put(presigned_url, file, {
        headers: { 'Content-Type': content_type },
        onUploadProgress: (ev) => {
          if (ev.total) {
            setUploadProgress(Math.round((ev.loaded / ev.total) * 100));
          }
        },
      });

      // Step 3: notify backend to start stem processing
      const completeToken = await getToken();
      await axios.post(`${API}/upload/complete`, { submission_id }, {
        headers: { Authorization: `Bearer ${completeToken}` }
      });

      setStage('done');
    } catch (err) {
      console.error(err);
      let detail;
      if (err.response?.status === 403) {
        const serverDetail = err.response?.data?.detail;
        detail = (!serverDetail || serverDetail === 'Forbidden')
          ? 'Your account is pending approval. We will email you once you are cleared to upload.'
          : serverDetail;
      } else if (err.response?.status === 422) {
        detail = validationMessage(err.response?.data?.detail)
          || 'Please refresh the page and try again.';
      } else if (err.response?.data?.detail) {
        detail = err.response.data.detail;
      } else if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
        detail = 'Could not reach the server. Check your connection or try again shortly.';
      } else if (err.response?.status >= 500) {
        detail = `Server error (${err.response.status}). Please try again.`;
      } else {
        detail = err.message || 'Something went wrong. Please try again.';
      }
      toast.error(detail);
      setStage('idle');
    }
  };

  if (stage === 'done') {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.21, 0.47, 0.32, 0.98] }}
          className="max-w-md w-full rounded-2xl border border-electric/30 bg-white/[0.02] p-12 text-center"
          data-testid="upload-success"
        >
          <CheckCircle2 size={56} className="text-cyan mx-auto" />
          <h2 className="mt-6 font-heading text-3xl font-semibold text-white">
            Track received.
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-400">
            We're separating your stems now. This usually takes a few minutes.
            Check the admin panel for status updates.
          </p>
          {submissionId && (
            <p className="mt-4 font-mono text-xs text-slate-600 break-all">
              ID: {submissionId}
            </p>
          )}
          <div className="mt-8 flex flex-col items-center gap-3">
            <Link
              to="/vault"
              className="inline-flex items-center gap-2 rounded-full bg-gradient-brand px-7 py-3 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)]"
            >
              Go to My Vault →
            </Link>
            <button
              onClick={resetForm}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-6 py-2.5 text-sm text-slate-300 transition-colors hover:border-electric/40 hover:text-white"
            >
              Upload another track
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  const isUploading = stage === 'uploading';

  return (
    <div data-testid="upload-page">
      <PageHero
        testid="upload-hero"
        label="Artist Upload"
        title="Submit Your Track"
        subtitle="Upload your master audio file. We'll handle stem separation automatically."
      />

      <section className="bg-ink py-20 lg:py-28">
        <div className="mx-auto max-w-2xl px-6 lg:px-8">
          <Reveal>
            <form
              data-testid="upload-form"
              onSubmit={handleSubmit}
              className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 md:p-10 space-y-6"
            >
              {/* Artist + Track Name */}
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="upload-artist" className="text-slate-300">
                    Artist Name *
                  </Label>
                  <Input
                    id="upload-artist"
                    data-testid="upload-artist-input"
                    value={form.artist_name}
                    onChange={update('artist_name')}
                    placeholder="Your stage name"
                    disabled={isUploading}
                    className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="upload-track" className="text-slate-300">
                    Track Name *
                  </Label>
                  <Input
                    id="upload-track"
                    data-testid="upload-track-input"
                    value={form.track_name}
                    onChange={update('track_name')}
                    placeholder="Song title"
                    disabled={isUploading}
                    className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  />
                </div>
              </div>

              {/* Genre */}
              <div className="space-y-2">
                <Label className="text-slate-300">Genre *</Label>
                <Select
                  value={form.genre}
                  onValueChange={(v) => setForm((f) => ({ ...f, genre: v }))}
                  disabled={isUploading}
                >
                  <SelectTrigger
                    data-testid="upload-genre-select"
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
              </div>

              {/* Moods */}
              <div className="space-y-2">
                <div className="flex items-baseline justify-between">
                  <Label className="text-slate-300">
                    Mood * <span className="text-slate-500">(pick 1 to 3)</span>
                  </Label>
                  <span className="text-xs text-slate-500">{moods.length} / {MAX_MOODS}</span>
                </div>
                <div className="flex flex-wrap gap-2" data-testid="upload-moods">
                  {MOODS.map((m) => {
                    const on = moods.includes(m);
                    return (
                      <button
                        key={m}
                        type="button"
                        aria-pressed={on}
                        onClick={() => toggleMood(m)}
                        disabled={isUploading}
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
                <div className="flex" data-testid="upload-vocals">
                  <div className="inline-flex rounded-full border border-white/10 p-1">
                    {VOCALS_OPTIONS.map((o) => (
                      <button
                        key={o.value}
                        type="button"
                        aria-pressed={vocals === o.value}
                        onClick={() => setVocals(o.value)}
                        disabled={isUploading}
                        className={`rounded-full px-5 py-1.5 text-sm transition-colors ${
                          vocals === o.value
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
                  <Label htmlFor="upload-bpm" className="text-slate-300">BPM *</Label>
                  <Input
                    id="upload-bpm"
                    data-testid="upload-bpm-input"
                    inputMode="decimal"
                    value={bpm}
                    onChange={(e) => {
                      const v = e.target.value.replace(/[^0-9.]/g, '');
                      const [whole, ...rest] = v.split('.');
                      setBpm(rest.length ? `${whole.slice(0, 3)}.${rest.join('').slice(0, 1)}` : whole.slice(0, 3));
                    }}
                    placeholder="e.g. 128"
                    disabled={isUploading || bpmUnsure}
                    className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  />
                  {!bpmUnsure && bpm && !bpmValid && (
                    <p className="text-xs text-red-400">BPM must be between {BPM_MIN} and {BPM_MAX}.</p>
                  )}
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
                    <Checkbox
                      data-testid="upload-bpm-unsure"
                      checked={bpmUnsure}
                      onCheckedChange={(v) => { setBpmUnsure(v === true); if (v === true) setBpm(''); }}
                      disabled={isUploading}
                      className={CHECKBOX_CLASS}
                    />
                    I'm unsure
                  </label>
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Key *</Label>
                  <Select
                    value={musicalKey}
                    onValueChange={setMusicalKey}
                    disabled={isUploading || keyUnsure}
                  >
                    <SelectTrigger
                      data-testid="upload-key-select"
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
                      data-testid="upload-key-unsure"
                      checked={keyUnsure}
                      onCheckedChange={(v) => { setKeyUnsure(v === true); if (v === true) setMusicalKey(''); }}
                      disabled={isUploading}
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

              {/* Consent */}
              <div className="space-y-3">
                <Label className="text-slate-300">How can this upload be used? *</Label>
                {[
                  {
                    id: 'consent-ai',
                    checked: consentAi,
                    onChange: setConsentAi,
                    title: 'Use this upload for AI training.',
                    help: 'Licensed to AI companies as training data.',
                  },
                  {
                    id: 'consent-sync',
                    checked: consentSync,
                    onChange: toggleSync,
                    title: 'Use this upload for sync placements.',
                    help: 'Listed in the oVoxi sync library for creators and brands to license.',
                  },
                ].map((c) => (
                  <label
                    key={c.id}
                    htmlFor={c.id}
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3.5 transition-colors ${
                      c.checked
                        ? 'border-electric/60 bg-electric/[0.06]'
                        : 'border-white/10 hover:border-electric/35'
                    }`}
                  >
                    <Checkbox
                      id={c.id}
                      data-testid={`upload-${c.id}`}
                      checked={c.checked}
                      onCheckedChange={(v) => c.onChange(v === true)}
                      disabled={isUploading}
                      className={CHECKBOX_CLASS}
                    />
                    <span>
                      <span className="block text-sm font-medium text-white">{c.title}</span>
                      <span className="mt-0.5 block text-xs text-slate-500">{c.help}</span>
                    </span>
                  </label>
                ))}
                {!consentAi && !consentSync && (
                  <p className="text-xs text-red-400">Choose at least one.</p>
                )}
              </div>

              {/* Splits (every upload) */}
              <RightsSection value={rights} onChange={setRights} disabled={isUploading} />

              {/* Sync details */}
              {consentSync && (
                <div
                  data-testid="upload-sync-panel"
                  className="space-y-6 rounded-2xl border border-cyan/25 bg-cyan/[0.03] p-5 sm:p-6"
                >
                  <div>
                    <h3 className="font-heading text-base font-semibold text-white">Sync details</h3>
                    <p className="mt-1 text-sm text-slate-400">
                      Buyers need these answers before your track can be licensed.
                    </p>
                  </div>

                  {/* Samples */}
                  <div className="space-y-2">
                    <Label className="text-slate-300">Samples *</Label>
                    <RadioGroup
                      value={intake.samples}
                      onValueChange={(v) => setIntakeField('samples', v)}
                      disabled={isUploading}
                      className="gap-2.5"
                    >
                      {SAMPLE_OPTIONS.map((o) => (
                        <label key={o.value} className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
                          <RadioGroupItem value={o.value} className={RADIO_CLASS} />
                          {o.label}
                        </label>
                      ))}
                    </RadioGroup>
                    <label className="flex cursor-pointer items-start gap-3 pt-2 text-sm text-slate-300">
                      <Checkbox
                        checked={intake.samples_attested}
                        onCheckedChange={(v) => setIntakeField('samples_attested', v === true)}
                        disabled={isUploading}
                        className={CHECKBOX_CLASS}
                      />
                      I confirm this is accurate and I have the rights described.
                    </label>
                  </div>

                  {/* Distributor */}
                  <div className="space-y-2">
                    <Label className="text-slate-300">Distributor *</Label>
                    <Select
                      value={intake.distributor}
                      onValueChange={(v) => setIntakeField('distributor', v)}
                      disabled={isUploading}
                    >
                      <SelectTrigger className="border-white/10 bg-ink text-white focus:ring-electric">
                        <SelectValue placeholder="Select distributor" />
                      </SelectTrigger>
                      <SelectContent className="border-white/10 bg-ink-2 text-white">
                        {DISTRIBUTORS.map((d) => (
                          <SelectItem key={d} value={d}>{d}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Content ID */}
                  <div className="space-y-2">
                    <Label className="text-slate-300">
                      Is this song registered in YouTube Content ID? *
                    </Label>
                    <RadioGroup
                      value={intake.content_id}
                      onValueChange={(v) => setIntakeField('content_id', v)}
                      disabled={isUploading}
                      className="flex flex-wrap gap-5"
                    >
                      {CONTENT_ID_OPTIONS.map((o) => (
                        <label key={o.value} className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-300">
                          <RadioGroupItem value={o.value} className={RADIO_CLASS} />
                          {o.label}
                        </label>
                      ))}
                    </RadioGroup>
                    <p className="text-xs leading-relaxed text-slate-500">
                      Songs in Content ID are not listed in the sync library, because buyers' videos would be claimed.
                    </p>
                  </div>

                  {/* PRO */}
                  <div className="space-y-3">
                    <Label className="text-slate-300">Performing rights (PRO)</Label>
                    <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
                      <Checkbox
                        checked={intake.pro_not_affiliated}
                        onCheckedChange={(v) => toggleNotAffiliated(v === true)}
                        disabled={isUploading}
                        className={CHECKBOX_CLASS}
                      />
                      I'm not affiliated with a PRO.
                    </label>
                    {!intake.pro_not_affiliated && (
                      <>
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <div className="space-y-2">
                            <Label className="text-slate-300">PRO *</Label>
                            <Select
                              value={intake.pro_name}
                              onValueChange={(v) => setIntakeField('pro_name', v)}
                              disabled={isUploading}
                            >
                              <SelectTrigger className="border-white/10 bg-ink text-white focus:ring-electric">
                                <SelectValue placeholder="Select PRO" />
                              </SelectTrigger>
                              <SelectContent className="border-white/10 bg-ink-2 text-white">
                                {PRO_ORGS.map((p) => (
                                  <SelectItem key={p} value={p}>{p}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="upload-ipi" className="text-slate-300">IPI number *</Label>
                            <Input
                              id="upload-ipi"
                              inputMode="numeric"
                              maxLength={11}
                              value={intake.ipi}
                              onChange={(e) => setIntakeField('ipi', e.target.value.replace(/\D/g, ''))}
                              placeholder="9 or 11 digits"
                              disabled={isUploading}
                              className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                            />
                            {intake.ipi && !IPI_PATTERN.test(intake.ipi) && (
                              <p className="text-xs text-red-400">IPI must be 9 or 11 digits.</p>
                            )}
                          </div>
                        </div>
                        <p className="text-xs text-slate-500">Your IPI number is in your PRO account.</p>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* File drop zone */}
              <div className="space-y-2">
                <Label className="text-slate-300">
                  Audio File *{' '}
                  <span className="text-slate-500">(MP3 or WAV, max 150 MB)</span>
                </Label>
                <div
                  data-testid="upload-dropzone"
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                  onClick={() => !isUploading && fileRef.current?.click()}
                  className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-10 text-center transition-colors ${
                    file
                      ? 'border-electric/50 bg-electric/[0.05]'
                      : 'border-white/20 bg-ink/60 hover:border-electric/40 hover:bg-electric/[0.04]'
                  } ${isUploading ? 'cursor-not-allowed opacity-60' : ''}`}
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
                    disabled={isUploading}
                  />
                </div>
              </div>

              {/* Upload progress */}
              {isUploading && (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>
                      {uploadProgress < 100
                        ? `Uploading to secure storage… ${uploadProgress}%`
                        : 'Queuing stem separation…'}
                    </span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-white/10 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-electric"
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadProgress}%` }}
                      transition={{ ease: 'linear' }}
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                data-testid="upload-submit-button"
                disabled={isUploading || !canSubmit}
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-gradient-brand px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              >
                {isUploading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Upload size={16} />
                )}
                {isUploading ? 'Uploading…' : 'Upload & Separate Stems'}
              </button>
              {!isUploading && !canSubmit && (
                <p className="text-xs text-slate-500" data-testid="upload-missing">
                  Still needed: {missing.join(', ')}.
                </p>
              )}
            </form>
          </Reveal>
        </div>
      </section>
    </div>
  );
};

export default UploadPage;
