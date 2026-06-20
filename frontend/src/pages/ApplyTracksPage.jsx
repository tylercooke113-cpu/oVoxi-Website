import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Plus, Trash2, Upload, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

const API = `https://ovoxi-website-production.up.railway.app/api`;
const MAX_FILE_SIZE = 20 * 1024 * 1024;

const ApplyTracksPage = () => {
  const [params] = useSearchParams();
  const email = params.get('email') || '';

  const [tracks, setTracks] = useState([{ id: Date.now(), title: '', file: null }]);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const addTrack = () =>
    setTracks((t) => [...t, { id: Date.now(), title: '', file: null }]);

  const removeTrack = (id) =>
    setTracks((t) => t.filter((tr) => tr.id !== id));

  const updateTitle = (id, title) =>
    setTracks((t) => t.map((tr) => (tr.id === id ? { ...tr, title } : tr)));

  const updateFile = (id, file) => {
    if (!file) return;
    if (file.size > MAX_FILE_SIZE) {
      toast.error(`${file.name} exceeds the 20 MB limit.`);
      return;
    }
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['mp3', 'wav'].includes(ext)) {
      toast.error(`${file.name} must be an MP3 or WAV file.`);
      return;
    }
    setTracks((t) => t.map((tr) => (tr.id === id ? { ...tr, file } : tr)));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error('Artist email is missing. Please start from Step 1.');
      return;
    }
    for (const track of tracks) {
      if (!track.title.trim()) {
        toast.error('Every track needs a title.');
        return;
      }
      if (!track.file) {
        toast.error('Every track needs an audio file.');
        return;
      }
    }

    setSubmitting(true);
    try {
      const fd = new FormData();
      tracks.forEach((t) => {
        fd.append('titles', t.title.trim());
        fd.append('files', t.file);
      });
      await axios.post(`${API}/artists/${encodeURIComponent(email)}/tracks`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDone(true);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.21, 0.47, 0.32, 0.98] }}
          className="max-w-md w-full rounded-2xl border border-electric/30 bg-white/[0.02] p-12 text-center"
        >
          <CheckCircle2 size={56} className="text-cyan mx-auto" />
          <h2 className="mt-6 font-heading text-3xl font-semibold text-white">
            You're in.
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-400">
            We'll be in touch within 5 business days.
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div data-testid="apply-tracks-page">
      <PageHero
        testid="apply-tracks-hero"
        label="Artist Application — Step 2 of 2"
        title="Upload Your Catalog"
        subtitle={
          email
            ? `Submitting tracks for ${email}. Add as many as you'd like.`
            : "Add as many tracks as you'd like."
        }
      />

      <section className="bg-ink py-20 lg:py-28">
        <div className="mx-auto max-w-2xl px-6 lg:px-8">
          <Reveal>
            <form
              data-testid="apply-tracks-form"
              onSubmit={handleSubmit}
              className="space-y-4"
            >
              <AnimatePresence initial={false}>
                {tracks.map((track, i) => (
                  <motion.div
                    key={track.id}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.22 }}
                    className="rounded-2xl border border-white/10 bg-white/[0.02] p-6"
                  >
                    <div className="flex items-center justify-between mb-5">
                      <span className="text-xs font-bold uppercase tracking-[0.2em] text-electric">
                        Track {i + 1}
                      </span>
                      {tracks.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeTrack(track.id)}
                          aria-label="Remove track"
                          className="text-slate-500 transition-colors hover:text-red-400"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>

                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label className="text-slate-300">Track Title *</Label>
                        <Input
                          value={track.title}
                          onChange={(e) => updateTitle(track.id, e.target.value)}
                          placeholder="Song title"
                          className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-slate-300">
                          Audio File * <span className="text-slate-500">(MP3 or WAV, max 20 MB)</span>
                        </Label>
                        <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-white/20 bg-ink/60 p-6 text-center transition-colors hover:border-electric/40 hover:bg-electric/[0.04]">
                          <Upload size={20} className="text-slate-500" />
                          {track.file ? (
                            <span className="text-sm font-medium text-white">
                              {track.file.name}
                            </span>
                          ) : (
                            <span className="text-sm text-slate-500">
                              Click to choose file
                            </span>
                          )}
                          <input
                            type="file"
                            accept=".mp3,.wav,audio/mpeg,audio/wav"
                            className="hidden"
                            onChange={(e) => updateFile(track.id, e.target.files?.[0])}
                          />
                        </label>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              <button
                type="button"
                onClick={addTrack}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.02] px-5 py-3 text-sm text-slate-300 transition-colors hover:border-electric/40 hover:text-white"
              >
                <Plus size={16} />
                Add Another Track
              </button>

              <button
                type="submit"
                data-testid="tracks-submit-button"
                disabled={submitting}
                className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-full bg-gradient-brand px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] disabled:opacity-60"
              >
                {submitting && <Loader2 size={16} className="animate-spin" />}
                {submitting ? 'Uploading…' : 'Submit Your Catalog'}
              </button>
            </form>
          </Reveal>
        </div>
      </section>
    </div>
  );
};

export default ApplyTracksPage;
