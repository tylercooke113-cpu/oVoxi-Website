import React, { useState, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Upload, CheckCircle2, Music2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
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

const API = `https://ovoxi-website-production.up.railway.app/api`;

const GENRES = [
  'Hip-Hop', 'R&B', 'Afrobeats', 'Trap', 'Soul',
  'Pop', 'Electronic', 'Latin', 'Reggaeton', 'Afropop', 'Other',
];

const MAX_BYTES = 200 * 1024 * 1024; // 200 MB

const STATUS_LABELS = {
  pending: 'Queued',
  uploaded: 'Uploaded',
  processing: 'Processing stems…',
  completed: 'Stems ready',
  failed: 'Processing failed',
};

const UploadPage = () => {
  const fileRef = useRef(null);

  const [form, setForm] = useState({ artist_name: '', track_name: '', genre: '' });
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [stage, setStage] = useState('idle'); // idle | uploading | processing | done | error
  const [submissionId, setSubmissionId] = useState(null);
  const [proRegistered, setProRegistered] = useState(false);
  const [proRegisterUs, setProRegisterUs] = useState(false);
  const [proOrg, setProOrg] = useState('');
  const [proOther, setProOther] = useState('');

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleFile = (f) => {
    if (!f) return;
    if (f.size > MAX_BYTES) {
      toast.error('File exceeds the 200 MB limit.');
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

    setStage('uploading');
    setUploadProgress(0);

    try {
      // Step 1: get presigned URL
      const { data: presignData } = await axios.post(`${API}/upload/presign`, {
        artist_name: form.artist_name,
        track_name: form.track_name,
        genre: form.genre,
        filename: file.name,
        pro_registered: proRegistered,
        pro_org: proRegistered ? (proOrg === 'Other' ? proOther : proOrg) : '',
        pro_register_us: proRegisterUs,
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
      await axios.post(`${API}/upload/complete`, { submission_id });

      setStage('done');
    } catch (err) {
      console.error(err);
      let detail;
      if (err.response?.data?.detail) {
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
              to="/admin"
              className="inline-flex items-center gap-2 rounded-full bg-electric px-7 py-3 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(0,102,255,0.55)]"
            >
              Go to My Vault →
            </Link>
            <button
              onClick={() => {
                setStage('idle');
                setFile(null);
                setForm({ artist_name: '', track_name: '', genre: '' });
                setSubmissionId(null);
                setUploadProgress(0);
              }}
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

              {/* PRO Registration */}
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 space-y-4">
                <span className="text-xs font-bold uppercase tracking-[0.2em] text-electric">
                  PRO Registration
                </span>

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={proRegistered}
                    onChange={(e) => {
                      setProRegistered(e.target.checked);
                      if (e.target.checked) setProRegisterUs(false);
                    }}
                    className="mt-0.5 accent-[#0066FF]"
                  />
                  <span className="text-sm text-slate-300">
                    These works are registered with a Performing Rights Organization
                  </span>
                </label>

                {proRegistered && (
                  <div className="ml-6 space-y-3">
                    <select
                      value={proOrg}
                      onChange={(e) => setProOrg(e.target.value)}
                      className="w-full rounded-lg border border-white/10 bg-ink px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-electric"
                    >
                      <option value="">Select PRO…</option>
                      <option value="ASCAP">ASCAP</option>
                      <option value="BMI">BMI</option>
                      <option value="Other">Other</option>
                    </select>
                    {proOrg === 'Other' && (
                      <input
                        type="text"
                        value={proOther}
                        onChange={(e) => setProOther(e.target.value)}
                        placeholder="Enter PRO name"
                        className="w-full rounded-lg border border-white/10 bg-ink px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-electric"
                      />
                    )}
                  </div>
                )}

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={proRegisterUs}
                    onChange={(e) => {
                      setProRegisterUs(e.target.checked);
                      if (e.target.checked) setProRegistered(false);
                    }}
                    className="mt-0.5 accent-[#0066FF]"
                  />
                  <span className="text-sm text-slate-300">
                    I would like oVoxi to register these songs on my behalf
                  </span>
                </label>
              </div>

              {/* File drop zone */}
              <div className="space-y-2">
                <Label className="text-slate-300">
                  Audio File *{' '}
                  <span className="text-slate-500">(MP3 or WAV, max 200 MB)</span>
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
                        MP3 or WAV up to 200 MB
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
                disabled={isUploading}
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-electric px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(0,102,255,0.55)] disabled:opacity-60 sm:w-auto"
              >
                {isUploading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Upload size={16} />
                )}
                {isUploading ? 'Uploading…' : 'Upload & Separate Stems'}
              </button>
            </form>
          </Reveal>
        </div>
      </section>
    </div>
  );
};

export default UploadPage;
