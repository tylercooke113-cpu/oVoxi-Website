import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, ArrowRight } from 'lucide-react';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
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

const ApplyPage = () => {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: '',
    email: '',
    spotify_url: '',
    genre: '',
    bio: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.spotify_url || !form.genre || !form.bio) {
      toast.error('Please fill in all required fields.');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/artists`, form);
      navigate(`/apply/tracks?email=${encodeURIComponent(form.email)}`);
    } catch (err) {
      if (err.response?.status === 409) {
        toast.error('An application with this email already exists.');
      } else {
        toast.error('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="apply-page">
      <PageHero
        testid="apply-hero"
        label="Artist Application — Step 1 of 2"
        title="Apply to Join oVoxi"
        subtitle="Tell us about yourself and your sound. We review every application."
      />

      <section className="bg-ink py-20 lg:py-28">
        <div className="mx-auto max-w-2xl px-6 lg:px-8">
          <Reveal>
            <form
              data-testid="apply-form"
              onSubmit={handleSubmit}
              className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 md:p-10 space-y-6"
            >
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="artist-name" className="text-slate-300">Artist Name *</Label>
                  <Input
                    id="artist-name"
                    data-testid="apply-name-input"
                    value={form.name}
                    onChange={update('name')}
                    placeholder="Your stage name"
                    className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="apply-email" className="text-slate-300">Email *</Label>
                  <Input
                    id="apply-email"
                    type="email"
                    data-testid="apply-email-input"
                    value={form.email}
                    onChange={update('email')}
                    placeholder="you@email.com"
                    className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="spotify-url" className="text-slate-300">Spotify URL *</Label>
                  <Input
                    id="spotify-url"
                    data-testid="apply-spotify-input"
                    value={form.spotify_url}
                    onChange={update('spotify_url')}
                    placeholder="open.spotify.com/artist/…"
                    className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Genre *</Label>
                  <Select
                    value={form.genre}
                    onValueChange={(v) => setForm((f) => ({ ...f, genre: v }))}
                  >
                    <SelectTrigger
                      data-testid="apply-genre-select"
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
              </div>

              <div className="space-y-2">
                <Label htmlFor="apply-bio" className="text-slate-300">Short Bio *</Label>
                <Textarea
                  id="apply-bio"
                  data-testid="apply-bio-input"
                  value={form.bio}
                  onChange={update('bio')}
                  rows={4}
                  placeholder="Tell us about your sound, influences, and what makes your music unique…"
                  className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                />
              </div>

              <button
                type="submit"
                data-testid="apply-submit-button"
                disabled={submitting}
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-gradient-brand px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] disabled:opacity-60 sm:w-auto"
              >
                {submitting ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <ArrowRight size={16} />
                )}
                {submitting ? 'Saving…' : 'Next — Upload Your Tracks'}
              </button>
            </form>
          </Reveal>
        </div>
      </section>
    </div>
  );
};

export default ApplyPage;
