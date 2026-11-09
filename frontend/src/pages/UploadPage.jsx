import React, { useState, useRef, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Loader2, Upload, CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth, useUser } from '@clerk/clerk-react';
import { accountFlags } from '../lib/account';
import { uploaderApi } from '../uploaders/api';
import { useAgreementStatus } from '../agreement/useAgreementStatus';
import AgreementModal from '../agreement/AgreementModal';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import SongForm, {
  emptySong,
  carryOverSong,
  songMissing,
  songHasData,
  MAX_SONGS,
} from '../upload/SongForm';
import SongSummaryRow from '../upload/SongSummaryRow';
import {
  useBatchUpload,
  APPROVAL_PENDING_MESSAGE,
  UPLOADS_PAUSED_MESSAGE,
  ARTIST_AGREEMENT_MESSAGE,
  ACTING_DENIED_MESSAGE,
  DAILY_LIMIT_MESSAGE,
} from '../upload/useBatchUpload';

// Kept verbatim for the three-file status contract in CLAUDE.md. These are the backend
// pipeline statuses, not the per-song batch statuses; they are mirrored, not used here.
// eslint-disable-next-line no-unused-vars
const STATUS_LABELS = {
  pending: 'Queued',
  uploaded: 'Uploaded',
  processing: 'Processing stems…',
  completed: 'Stems ready',
  failed: 'Processing failed',
};

const UploadPage = () => {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const { user } = useUser();
  const navigate = useNavigate();
  // Brief 28 D3: an uploader-only login never uploads for itself and never signs the Artist
  // Agreement; it only uploads for the artists who authorized it.
  const uploaderOnly = accountFlags(user, isSignedIn).isUploaderOnly;
  const { status, refresh: refreshAgreement, needsSignature } =
    useAgreementStatus(getToken, isLoaded && isSignedIn && !uploaderOnly);
  const [agreementOpen, setAgreementOpen] = useState(false);
  const signedRef = useRef(false);

  // "Uploading for": '' is the signed-in artist; otherwise an artist user id (X-Acting-For).
  const [artists, setArtists] = useState(null);   // null while loading
  // Brief 28 D4: the Vault's "Upload for {artist}" opens this page with ?for=<artist id>.
  const [actingId, setActingId] = useState(
    () => new URLSearchParams(window.location.search).get('for') || '');
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return undefined;
    let live = true;
    uploaderApi.artists(getToken)
      .then((list) => { if (live) setArtists(list); })
      .catch(() => { if (live) setArtists([]); });
    return () => { live = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn]);
  useEffect(() => {
    // A ?for= that is not one of this user's artists falls back (never uploads for an unknown id).
    if (actingId && artists && !artists.some((a) => a.artist_user_id === actingId)) { setActingId(''); return; }
    if (uploaderOnly && !actingId && artists?.length) setActingId(artists[0].artist_user_id);
  }, [uploaderOnly, actingId, artists]);
  const acting = (artists || []).find((a) => a.artist_user_id === actingId) || null;

  useEffect(() => {
    if (needsSignature && !actingId && !uploaderOnly) setAgreementOpen(true);
  }, [needsSignature, actingId, uploaderOnly]);

  const [songs, setSongs] = useState(() => [emptySong()]);
  const [activeKey, setActiveKey] = useState(() => songs[0].key);
  const [phase, setPhase] = useState('edit'); // edit | done

  const { running, run } = useBatchUpload({ getToken, actingFor: acting ? acting.artist_user_id : null });

  // Scroll a freshly added song into view once it becomes active.
  const activeRef = useRef(null);
  const scrollOnNextActive = useRef(false);
  useEffect(() => {
    if (scrollOnNextActive.current && activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      scrollOnNextActive.current = false;
    }
  }, [activeKey]);

  const patchSong = useCallback((key, partial) => {
    setSongs((prev) => prev.map((s) => (s.key === key ? { ...s, ...partial } : s)));
  }, []);

  if (isLoaded && !isSignedIn) return <Navigate to='/login' replace />;

  // An uploader-only login with no active authorization has nothing to upload to.
  if (uploaderOnly && artists !== null && artists.length === 0) {
    return (
      <div data-testid="upload-page">
        <PageHero testid="upload-hero" label="Authorized Uploader" title="No artists yet"
          subtitle="You can upload once an artist adds you as an Authorized Uploader." />
        <section className="bg-ink py-20">
          <div className="mx-auto max-w-xl px-6 text-center text-sm text-slate-400" data-testid="upload-no-artists">
            When an artist adds you and you sign the invitation they send, they show up here.
            If you already signed one, the artist may have revoked it.
          </div>
        </section>
      </div>
    );
  }
  if (uploaderOnly && !acting) {
    return <div className="flex min-h-screen items-center justify-center bg-ink"><Loader2 size={28} className="animate-spin text-electric" /></div>;
  }

  const showPicker = !!artists?.length;
  const switchTarget = (id) => {
    if (id === actingId || running) return;
    if (songs.some(songHasData)
        && !window.confirm("Switch who you're uploading for? The songs in this batch will be cleared.")) return;
    const fresh = emptySong();
    setSongs([fresh]);
    setActiveKey(fresh.key);
    setActingId(id);
  };
  const picker = showPicker && (
    <div className="mb-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5" data-testid="upload-acting-picker">
      <div className="mb-2 text-sm font-medium text-slate-300">Uploading for</div>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Uploading for">
        {[...(uploaderOnly ? [] : [{ artist_user_id: '', artist_name: 'Me' }]), ...artists].map((a) => {
          const on = a.artist_user_id === actingId;
          return (
            <button key={a.artist_user_id || 'me'} type="button" role="radio" aria-checked={on}
              disabled={running} onClick={() => switchTarget(a.artist_user_id)}
              data-testid={`upload-for-${a.artist_user_id || 'me'}`}
              className={`rounded-full border px-4 py-1.5 text-sm transition-colors disabled:opacity-50 ${
                on ? 'border-electric bg-electric/15 text-white' : 'border-white/10 text-slate-300 hover:border-electric/40'}`}>
              {a.artist_name}{a.is_ovoxi ? ' (as OVOXI)' : ''}
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {acting
          ? `Songs go to ${acting.artist_name}'s catalog. You can set only the uses they authorized. Uploaders can add up to 250 songs a day to their catalog, shared by all of their uploaders.`
          : 'Songs go to your own catalog.'}
      </p>
    </div>
  );
  const banner = acting && (
    <div className="sticky top-16 z-30 border-b border-electric/40 bg-gradient-to-r from-[#B44FD4]/25 to-[#6B7FD4]/25 px-4 py-2.5 text-center text-sm text-white"
      data-testid="upload-acting-banner">
      Acting for <b className="font-semibold">{acting.artist_name}</b>
      {acting.is_ovoxi ? ' as OVOXI' : ' as Authorized Uploader'}. Songs go to their catalog under their Artist Agreement.
    </div>
  );

  const activeSong = songs.find((s) => s.key === activeKey);
  const activeMissing = activeSong ? songMissing(activeSong) : [];
  const atMax = songs.length >= MAX_SONGS;

  const handleEdit = (key) => setActiveKey(key);

  const handleRemove = (key) => {
    const song = songs.find((s) => s.key === key);
    if (songHasData(song)
        && !window.confirm('Remove this song? Anything you entered will be lost.')) {
      return;
    }
    const remaining = songs.filter((s) => s.key !== key);
    if (remaining.length === 0) {
      const fresh = emptySong();
      setSongs([fresh]);
      setActiveKey(fresh.key);
      return;
    }
    setSongs(remaining);
    if (key === activeKey) setActiveKey(remaining[remaining.length - 1].key);
  };

  const handleAddSong = () => {
    if (activeMissing.length > 0 || atMax) return;
    const next = carryOverSong(activeSong);
    setSongs((prev) => [...prev, next]);
    setActiveKey(next.key);
    scrollOnNextActive.current = true;
  };

  const startRun = async (list) => {
    if (!list.length) return;
    const keys = new Set(list.map((s) => s.key));
    setSongs((prev) => prev.map((s) => (keys.has(s.key)
      ? { ...s, status: 'queued', progress: 0, error: null }
      : s)));
    const { stopReason, failed } = await run(list, patchSong);
    if (stopReason === 'agreement') {
      if (acting || uploaderOnly) { toast.error(ARTIST_AGREEMENT_MESSAGE); return; }
      await refreshAgreement();
      setAgreementOpen(true);
      return;
    }
    if (stopReason === 'artist_agreement') { toast.error(ARTIST_AGREEMENT_MESSAGE); return; }
    if (stopReason === 'acting_denied') { toast.error(ACTING_DENIED_MESSAGE); return; }
    if (stopReason === 'daily_limit') { toast.error(DAILY_LIMIT_MESSAGE); return; }
    if (stopReason === 'approval') { toast.error(APPROVAL_PENDING_MESSAGE); return; }
    if (stopReason === 'paused') { toast.error(UPLOADS_PAUSED_MESSAGE); return; }
    // Brief 25b C6 / decision 9: once every file is received, go to the Vault. Mastering,
    // stems and checks continue in the background, with status shown there.
    // Acting: stay here (the artist's Vault view is Part D4); the done screen lists the batch.
    if (!stopReason && !failed && acting) {
      toast.success(`${list.length === 1 ? 'Song' : `${list.length} songs`} received for ${acting.artist_name}.`);
      setPhase('done');
      return;
    }
    if (!stopReason && !failed) {
      toast.success(list.length === 1 ? 'Song received. Processing continues in your Vault.'
        : `${list.length} songs received. Processing continues in your Vault.`);
      navigate('/vault');
      return;
    }
    setPhase('done');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const incompleteIdx = songs.findIndex((s) => songMissing(s).length > 0);
    if (incompleteIdx !== -1) {
      const s = songs[incompleteIdx];
      setActiveKey(s.key);
      toast.error(`Song ${incompleteIdx + 1} still needs: ${songMissing(s).join(', ')}.`);
      return;
    }
    // Resume safely: only songs not already received are (re)sent.
    startRun(songs.filter((s) => s.status !== 'received'));
  };

  const handleRetryFailed = () => startRun(songs.filter((s) => s.status === 'failed'));

  const handleUploadMore = () => {
    const fresh = emptySong();
    setSongs([fresh]);
    setActiveKey(fresh.key);
    setPhase('edit');
  };

  const receivedCount = songs.filter((s) => s.status === 'received').length;
  const failedCount = songs.filter((s) => s.status === 'failed').length;
  const submitLabel = `Upload ${songs.length} song${songs.length === 1 ? '' : 's'}`;

  // ---- Done screen ---------------------------------------------------------
  if (phase === 'done') {
    return (
      <div data-testid="upload-page">
        {banner}
        <PageHero
          testid="upload-hero"
          label={acting ? `Uploading for ${acting.artist_name}` : 'Artist Upload'}
          title="Upload complete"
          subtitle="Here's how your batch did."
        />
        <section className="bg-ink py-20 lg:py-28">
          <div className="mx-auto max-w-2xl px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, ease: [0.21, 0.47, 0.32, 0.98] }}
              className="rounded-2xl border border-electric/30 bg-white/[0.02] p-8 md:p-10"
              data-testid="upload-success"
            >
              <div className="flex items-center gap-3">
                <CheckCircle2 size={28} className="text-cyan" />
                <h2 className="font-heading text-2xl font-semibold text-white">
                  {receivedCount} of {songs.length} songs received
                </h2>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                We're separating your stems now. Each song takes a few minutes, and songs are
                processed a couple at a time.
              </p>

              <div className="mt-6 space-y-3">
                {songs.map((song, i) => (
                  <SongSummaryRow key={song.key} song={song} index={i} locked />
                ))}
              </div>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                {failedCount > 0 && (
                  <button
                    type="button"
                    data-testid="upload-retry-failed"
                    onClick={handleRetryFailed}
                    disabled={running}
                    className="inline-flex items-center justify-center gap-2 rounded-full bg-gradient-brand px-6 py-2.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {running ? <Loader2 size={16} className="animate-spin" /> : null}
                    Retry failed songs
                  </button>
                )}
                {acting && (
                  <Link
                    to={`/vault?for=${encodeURIComponent(acting.artist_user_id)}`}
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-6 py-2.5 text-sm text-slate-200 transition-colors hover:border-electric/40 hover:text-white"
                  >
                    Go to {acting.artist_name}'s Vault
                  </Link>
                )}
                {!acting && (
                  <Link
                    to="/vault"
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-6 py-2.5 text-sm text-slate-200 transition-colors hover:border-electric/40 hover:text-white"
                  >
                    Go to My Vault →
                  </Link>
                )}
                <button
                  type="button"
                  onClick={handleUploadMore}
                  disabled={running}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-6 py-2.5 text-sm text-slate-300 transition-colors hover:border-electric/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Upload more songs
                </button>
              </div>
            </motion.div>
          </div>
        </section>
        <AgreementModal
          open={agreementOpen}
          onClose={() => { setAgreementOpen(false); if (!signedRef.current) navigate('/vault'); }}
          onSigned={() => { signedRef.current = true; refreshAgreement(); }}
          getToken={getToken}
          prefill={status?.prefill}
          previousSigned={status?.previous_signed}
        />
      </div>
    );
  }

  // ---- Edit / running screen ----------------------------------------------
  return (
    <div data-testid="upload-page">
      {banner}
      <PageHero
        testid="upload-hero"
        label={acting ? `Uploading for ${acting.artist_name}` : 'Artist Upload'}
        title="Submit Your Tracks"
        subtitle="Upload up to 15 tracks in one batch. We'll handle stem separation automatically."
      />

      <section className="bg-ink py-20 lg:py-28">
        <div className="mx-auto max-w-2xl px-6 lg:px-8">
          {picker}
          <Reveal>
            <form data-testid="upload-form" onSubmit={handleSubmit} className="space-y-5">
              {songs.map((song, i) => {
                if (!running && song.key === activeKey) {
                  return (
                    <div key={song.key} ref={activeRef} className="space-y-4">
                      <SongForm
                        value={song}
                        index={i}
                        onChange={(partial) => patchSong(song.key, partial)}
                        disabled={running}
                        agreementStatus={status}
                        getToken={getToken}
                        acting={acting}
                      />

                      {/* + Add another song sits under the open song */}
                      {atMax ? (
                        <p className="text-center text-xs text-slate-500" data-testid="upload-at-max">
                          15 songs is the most per batch. Upload these, then start a new batch.
                        </p>
                      ) : (
                        <div className="text-center">
                          <button
                            type="button"
                            data-testid="upload-add-song"
                            onClick={handleAddSong}
                            disabled={activeMissing.length > 0}
                            className="inline-flex items-center justify-center gap-2 rounded-full border border-electric/40 bg-electric/10 px-5 py-2 text-sm font-medium text-white transition-all duration-300 hover:bg-electric/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-transparent disabled:text-slate-500"
                          >
                            + Add another song
                          </button>
                          {activeMissing.length > 0 && (
                            <p className="mt-2 text-xs text-slate-500" data-testid="upload-add-blocked">
                              Finish this song first: missing {activeMissing.join(', ')}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                }
                return (
                  <SongSummaryRow
                    key={song.key}
                    song={song}
                    index={i}
                    locked={running}
                    onEdit={() => handleEdit(song.key)}
                    onRemove={() => handleRemove(song.key)}
                  />
                );
              })}

              {running && (
                <div
                  className="flex items-center justify-center gap-2 rounded-xl border border-electric/30 bg-electric/[0.05] px-5 py-4 text-sm text-slate-300"
                  data-testid="upload-running-notice"
                  aria-live="polite"
                >
                  <Loader2 size={16} className="animate-spin text-electric" />
                  Uploading your songs. Keep this tab open until it finishes.
                </div>
              )}

              {!running && (
                <div className="pt-2">
                  <button
                    type="submit"
                    data-testid="upload-submit-button"
                    className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-gradient-brand px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] sm:w-auto"
                  >
                    <Upload size={16} />
                    {submitLabel}
                  </button>
                  {activeMissing.length > 0 && (
                    <p className="mt-3 text-xs text-slate-500" data-testid="upload-missing">
                      Still needed: {activeMissing.join(', ')}.
                    </p>
                  )}
                </div>
              )}
            </form>
          </Reveal>
        </div>
      </section>

      <AgreementModal
        open={agreementOpen}
        onClose={() => { setAgreementOpen(false); if (!signedRef.current) navigate('/vault'); }}
        onSigned={() => { signedRef.current = true; refreshAgreement(); }}
        getToken={getToken}
        prefill={status?.prefill}
        previousSigned={status?.previous_signed}
      />
    </div>
  );
};

export default UploadPage;
