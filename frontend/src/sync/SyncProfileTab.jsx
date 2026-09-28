import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { api, errorMessage } from './api';
import { reasonText } from './labels';
import { Avatar } from './PublicPageParts';

const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_PHOTO = 10 * 1024 * 1024;

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
  const [photoUrl, setPhotoUrl] = useState(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const p = await api.getProfile(getToken);
        if (!alive) return;
        if (p && p.slug) {
          setSlug(p.slug);
          setPhotoUrl(p.photo_url || null);
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

  const uploadPhoto = async (file) => {
    if (!file) return;
    if (!PHOTO_TYPES.includes(file.type)) { toast.error('Use a JPEG, PNG or WebP image.'); return; }
    if (file.size > MAX_PHOTO) { toast.error('Photo must be 10 MB or smaller.'); return; }
    setPhotoBusy(true);
    try {
      const { presigned_url: url, upload_id: uploadId, content_type: type } =
        await api.presignPhoto(getToken, { content_type: file.type, file_size: file.size });
      await axios.put(url, file, { headers: { 'Content-Type': type } });
      const p = await api.completePhoto(getToken, uploadId);
      setPhotoUrl(p.photo_url || null);
      toast.success('Photo updated.');
    } catch (err) {
      toast.error(errorMessage(err, 'Photo upload failed. Please try again.'));
    } finally {
      setPhotoBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const removePhoto = async () => {
    setPhotoBusy(true);
    try { await api.deletePhoto(getToken); setPhotoUrl(null); toast.success('Photo removed.'); }
    catch (err) { toast.error(errorMessage(err)); } finally { setPhotoBusy(false); }
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
        <div className="mb-5 flex flex-wrap items-center gap-4" data-testid="profile-photo">
          <Avatar profile={{ photo_url: photoUrl, display_name: form.display_name }} size={72} />
          {slug ? (
            <div className="flex flex-wrap items-center gap-2">
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                onChange={(e) => uploadPhoto(e.target.files?.[0])} data-testid="photo-input" />
              <button type="button" disabled={photoBusy} onClick={() => fileRef.current?.click()}
                className="rounded-full border border-white/10 px-4 py-1.5 text-sm text-slate-300 hover:text-white disabled:opacity-50">
                {photoBusy ? 'Uploading…' : photoUrl ? 'Change photo' : 'Upload photo'}
              </button>
              {photoUrl && !photoBusy && (
                <button type="button" onClick={removePhoto} className="text-xs text-slate-500 hover:text-white">Remove photo</button>
              )}
              <span className="w-full text-xs text-slate-500">JPEG, PNG or WebP up to 10 MB. We crop it square and remove location data.</span>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Save your profile first, then add a photo.</p>
          )}
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
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="submit" disabled={saving || !form.display_name.trim()}
            className="rounded-full bg-gradient-brand px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
            {saving ? 'Saving…' : 'Save profile'}
          </button>
          {slug && (
            <a href={`/artist/${slug}`} target="_blank" rel="noopener noreferrer"
              className="rounded-full border border-white/10 px-5 py-2.5 text-sm text-slate-300 hover:text-white">View my page</a>
          )}
        </div>
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
