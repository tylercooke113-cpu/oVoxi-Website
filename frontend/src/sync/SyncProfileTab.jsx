import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { api, errorMessage } from './api';
import { reasonText } from './labels';

// Vault "Sync Profile" tab (PRD-03 4.3). Photo arrives in Phase 4b.

const EMPTY = { display_name: '', bio: '', location: '', spotify_url: '', instagram_url: '' };
const FIELD = 'border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric';

const previewSlug = (name) =>
  name.normalize('NFKD').replace(/[^\x00-\x7F]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'artist';

const statusOf = (t) => {
  if (t.status === 'CONFLICT' || t.sync_status === 'conflict') return ['text-red-400', 'Conflict'];
  if (t.sync_status === 'cleared' && t.on_sync_profile) return ['text-green-400', 'Live'];
  if (t.sync_status === 'needs_docs' || t.sync_status === 'cleared') {
    const first = (t.sync_reasons || [])[0];
    return ['text-amber-400', first ? `Needs docs: ${reasonText(first)}` : 'Needs docs'];
  }
  return ['text-cyan', 'Processing'];
};

const SyncProfileTab = ({ getToken, tracks }) => {
  const [form, setForm] = useState(EMPTY);
  const [slug, setSlug] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const p = await api.getProfile(getToken);
        if (!alive) return;
        if (p && p.slug) {
          setSlug(p.slug);
          setForm({ ...EMPTY, ...Object.fromEntries(Object.keys(EMPTY).map((k) => [k, p[k] || ''])) });
        }
      } catch (err) {
        toast.error(errorMessage(err, 'Could not load your profile.'));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [getToken]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const p = await api.putProfile(getToken, form);
      setSlug(p.slug);
      toast.success('Profile saved.');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const syncTracks = tracks.filter((t) => !t.legacy && t.consent?.sync);

  if (loading) {
    return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-electric" size={28} /></div>;
  }

  return (
    <div className="flex flex-col gap-4" data-testid="vault-sync-profile">
      {!slug && (
        <p className="text-sm text-slate-400">Submit your music to your sync library. Start with your profile.</p>
      )}
      <form onSubmit={save} className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
        <div className="mb-5 rounded-xl border border-dashed border-white/10 p-3 text-sm text-slate-500">
          Profile photo: coming with your public profile page.
        </div>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="sp-name" className="text-slate-300">Display name *</Label>
            <Input id="sp-name" value={form.display_name} onChange={set('display_name')} maxLength={80} className={FIELD} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="sp-loc" className="flex justify-between text-slate-300">
              Location <span className="text-xs font-normal text-slate-500">{form.location.length} / 80</span>
            </Label>
            <Input id="sp-loc" value={form.location} onChange={set('location')} maxLength={80} className={FIELD} />
          </div>
        </div>
        <div className="mt-5 space-y-2">
          <Label htmlFor="sp-bio" className="flex justify-between text-slate-300">
            Bio <span className="text-xs font-normal text-slate-500">{form.bio.length} / 500</span>
          </Label>
          <Textarea id="sp-bio" value={form.bio} onChange={set('bio')} maxLength={500} rows={5}
            placeholder="Tell buyers about your sound." className={FIELD} />
        </div>
        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="sp-spotify" className="text-slate-300">Spotify artist link</Label>
            <Input id="sp-spotify" value={form.spotify_url} onChange={set('spotify_url')}
              placeholder="https://open.spotify.com/artist/..." className={FIELD} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="sp-ig" className="text-slate-300">Instagram link</Label>
            <Input id="sp-ig" value={form.instagram_url} onChange={set('instagram_url')}
              placeholder="https://instagram.com/..." className={FIELD} />
          </div>
        </div>
        <div className="mt-5 rounded-lg border border-dashed border-white/10 px-3 py-2.5 text-sm text-slate-400">
          Your profile address: <b className="font-medium text-white">ovoxi.net/artist/{slug || previewSlug(form.display_name)}</b>
          <p className="mt-0.5 text-xs text-slate-500">
            {slug ? 'This address is permanent, so links you share keep working.'
              : 'Set on first save. It can\'t be changed afterwards, so links you share keep working.'}
          </p>
        </div>
        <button type="submit" disabled={saving || !form.display_name.trim()}
          className="mt-5 rounded-full bg-gradient-brand px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
          {saving ? 'Saving…' : 'Save profile'}
        </button>
      </form>

      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
        <p className="mb-3 text-[11px] uppercase tracking-[0.14em] text-slate-500">Your sync tracks</p>
        {syncTracks.length === 0 ? (
          <p className="text-sm text-slate-500">No sync tracks yet. Turn on Sync placements on a track in My Tracks.</p>
        ) : syncTracks.map((t) => {
          const [color, text] = statusOf(t);
          return (
            <div key={t.id} className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 px-3 py-2.5 text-sm">
              <span className="text-white">{t.track_name}</span>
              <span className={`font-medium ${color}`}>● {text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SyncProfileTab;
