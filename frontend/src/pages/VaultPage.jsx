import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useUser, useAuth, SignOutButton } from '@clerk/clerk-react';
import { Navigate, useSearchParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Loader2, Music2, ExternalLink, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import TrackSyncPanel from '../sync/TrackSyncPanel';
import NotIntendedRemove from '../sync/NotIntendedRemove';
import SyncProfileTab from '../sync/SyncProfileTab';
import WalletTab from '../wallet/WalletTab';
import { accountFlags } from '../lib/account';
import { useAgreementStatus } from '../agreement/useAgreementStatus';
import { openAgreementPdf, formatSignedDate } from '../agreement/agreementApi';
import AgreementModal from '../agreement/AgreementModal';
import AuthorizedUploadersTab from '../uploaders/AuthorizedUploadersTab';
import { uploaderApi } from '../uploaders/api';
import { authed, actingGetToken } from '../sync/api';

const API = 'https://ovoxi-website-production.up.railway.app/api';

const TrackStatusBadge = ({ status, submissionId, canAppeal = true }) => {
  const inProgress = {
    pending:    { text: 'Queued',               color: 'text-slate-400' },
    uploaded:   { text: 'Uploaded',             color: 'text-blue-400' },
    mastering:  { text: 'Mastering…',      color: 'text-purple-400', spin: true },
    processing: { text: 'Processing stems…', color: 'text-yellow-400', spin: true },
    scanning:   { text: 'Checking…',       color: 'text-blue-400',   spin: true },
  };
  if (inProgress[status]) {
    const { text, color, spin } = inProgress[status];
    return (
      <span className={`inline-flex items-center gap-1 text-sm font-medium ${color}`}>
        {spin && <Loader2 size={14} className="animate-spin" />}
        {text}
      </span>
    );
  }
  if (status === 'completed' || status === 'CLEARED') {
    return (
      <span className="inline-flex items-center gap-1 text-sm font-medium text-green-400">
        <CheckCircle2 size={14} />
        {status === 'completed' ? 'Ready' : 'Cleared'}
      </span>
    );
  }
  if (status === 'NEEDS_DOCS' || status === 'SCAN_ERROR') {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-red-400">
        <XCircle size={14} />
        Under Review
      </span>
    );
  }
  if (status === 'CONFLICT') {
    return (
      <div className="flex flex-col items-end gap-2">
        <span className="inline-flex items-center gap-1.5 text-sm font-medium text-red-400">
          <XCircle size={14} />
          this recording appears to match existing copyrighted material
        </span>
        {canAppeal && <Link
          to={`/appeal/${submissionId}`}
          className="rounded-full border border-electric/40 bg-electric/[0.08] px-4 py-1.5 text-xs font-semibold text-electric hover:bg-electric/[0.16] transition-colors"
        >
          File Appeal
        </Link>}
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 text-sm font-medium text-red-400">
        <XCircle size={14} />
        Failed
      </span>
    );
  }
  return <span className="text-sm font-medium text-slate-400">{status}</span>;
};

const VaultPage = () => {
  const { isLoaded, isSignedIn, user } = useUser();
  const { getToken } = useAuth();
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tracksLoaded, setTracksLoaded] = useState(false);   // latches true after the first fetch
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState({ profile: 'profile', wallet: 'wallet', uploaders: 'uploaders' }[searchParams.get('tab')] || 'tracks');
  const updateTrack = useCallback((t) => setTracks((all) => all.map((x) => (x.id === t.id ? t : x))), []);
  const navigate = useNavigate();
  const uploaderOnly = accountFlags(user, isSignedIn).isUploaderOnly;

  // Brief 28 D4: acting mode. ?for=<artist id> (or, for an uploader-only login, its first
  // artist) shows that artist's catalog through X-Acting-For. Everything else stays hidden.
  const [artists, setArtists] = useState(null);     // null while loading
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return undefined;
    let live = true;
    uploaderApi.artists(getToken).then((l) => live && setArtists(l)).catch(() => live && setArtists([]));
    return () => { live = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn]);
  const forParam = searchParams.get('for') || '';
  const actingId = forParam || (uploaderOnly && artists?.length ? artists[0].artist_user_id : '');
  const acting = actingId ? (artists || []).find((a) => a.artist_user_id === actingId) || null : null;
  const actingWaiting = (!!actingId || uploaderOnly) && artists === null;
  const actingUnknown = !!forParam && artists !== null && !acting;
  const tokenFn = useMemo(
    () => (acting ? actingGetToken(getToken, acting.artist_user_id) : getToken),
  // eslint-disable-next-line react-hooks/exhaustive-deps
    [acting?.artist_user_id, getToken]);
  const setVaultFor = (id) => setSearchParams(id ? { for: id } : {});

  const { status, refresh: refreshAgreement, needsSignature } =
    useAgreementStatus(getToken, isLoaded && isSignedIn && !uploaderOnly);
  const [agreementOpen, setAgreementOpen] = useState(false);
  const onUpload = () => (acting ? navigate(`/upload?for=${encodeURIComponent(acting.artist_user_id)}`)
    : needsSignature ? setAgreementOpen(true) : navigate('/upload'));

  const fetchTracks = useCallback(async () => {
    if (!isLoaded || !isSignedIn || actingWaiting || actingUnknown) return;
    if (uploaderOnly && !acting) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await axios.get(`${API}/vault/tracks`, await authed(tokenFn));
      setTracks(res.data);
    } catch (err) {
      console.error('Failed to fetch tracks', err);
    } finally {
      setLoading(false);
      setTracksLoaded(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoaded, isSignedIn, tokenFn, actingWaiting, actingUnknown, uploaderOnly]);

  useEffect(() => {
    fetchTracks();
  }, [fetchTracks]);

  // Brief 23 E4: open the agreement straight away for a signed-in non-buyer who needs to sign
  // (as the upload page does). Buyers are redirected below; this also guards against the flash.
  useEffect(() => {
    const fl = accountFlags(user, isSignedIn);
    if (needsSignature && !fl.isBuyerOnly && !fl.isUploaderOnly && !forParam) setAgreementOpen(true);
  }, [needsSignature, user, isSignedIn, forParam]);

  if (!isLoaded) return null;
  if (!isSignedIn) return <Navigate to="/login" replace />;
  if (accountFlags(user, isSignedIn).isBuyerOnly) return <Navigate to="/account" replace />;
  // Brief 28 D4: an uploader-only login has no catalog of its own, only the artists' it acts for.
  if (uploaderOnly && artists !== null && artists.length === 0) {
    return (
      <div className="min-h-screen bg-ink px-6 pb-16 pt-28" data-testid="vault-no-artists">
        <div className="mx-auto max-w-xl rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center">
          <h1 className="font-heading text-2xl font-semibold text-white">No artists yet</h1>
          <p className="mt-3 text-sm text-slate-400">
            When an artist adds you as an Authorized Uploader and you sign their invitation, their catalog shows up here.
          </p>
        </div>
      </div>
    );
  }
  if (actingUnknown) {
    return (
      <div className="min-h-screen bg-ink px-6 pb-16 pt-28" data-testid="vault-acting-unknown">
        <div className="mx-auto max-w-xl rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center">
          <h1 className="font-heading text-2xl font-semibold text-white">Not available</h1>
          <p className="mt-3 text-sm text-slate-400">You're not an Authorized Uploader for this artist, or their authorization has ended.</p>
          {!uploaderOnly && (
            <button type="button" onClick={() => setVaultFor('')} className="mt-5 text-sm text-[#4FC3F7] hover:underline">Back to my Vault</button>
          )}
        </div>
      </div>
    );
  }
  if (actingWaiting) {
    return <div className="flex min-h-screen items-center justify-center bg-ink"><Loader2 className="animate-spin text-electric" size={32} /></div>;
  }

  const shownTab = acting ? 'tracks' : tab;
  const TABS = acting ? [['tracks', 'Tracks']]
    : [['tracks', 'My Tracks'], ['profile', 'Sync Profile'], ['wallet', 'Wallet'], ['uploaders', 'Authorized uploaders']];

  return (
    <div className="min-h-screen bg-ink pt-24 pb-16 px-6">
      {acting && (
        <div className="-mx-6 mb-6 border-y border-electric/40 bg-gradient-to-r from-[#B44FD4]/25 to-[#6B7FD4]/25 px-4 py-2.5 text-center text-sm text-white"
          data-testid="vault-acting-banner">
          Acting for <b className="font-semibold">{acting.artist_name}</b>
          {acting.is_ovoxi ? ' as OVOXI' : ' as Authorized Uploader'}.
          {!uploaderOnly && (
            <button type="button" onClick={() => setVaultFor('')} className="ml-3 rounded-full border border-white/20 px-3 py-0.5 text-xs hover:bg-white/10">
              Back to my Vault
            </button>
          )}
        </div>
      )}
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-10">
          <div>
            <h1 className="font-heading text-3xl font-semibold text-white">
              {acting ? `${acting.artist_name}'s Vault` : 'My Vault'}
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              {acting ? `Viewing as ${[user?.firstName, user?.lastName].filter(Boolean).join(' ') || 'Authorized Uploader'}` : `${user?.firstName || ''} ${user?.lastName || ''}`}
            </p>
            {!acting && status?.signed && status.agreement && (
              <p className="mt-1.5 text-xs text-slate-500">
                Artist Agreement signed {formatSignedDate(status.agreement.signed_at)} ·{' '}
                <button type="button" onClick={() => openAgreementPdf(getToken)} className="text-[#4FC3F7] hover:underline">
                  Download PDF
                </button>
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {!!artists?.length && (
              <label className="flex items-center gap-2 text-xs text-slate-500" data-testid="vault-for-picker">
                Vault for
                <select value={actingId} onChange={(e) => setVaultFor(e.target.value)}
                  className="rounded-lg border border-white/10 bg-black px-2.5 py-1.5 text-sm text-white">
                  {!uploaderOnly && <option value="">Me</option>}
                  {artists.map((a) => (
                    <option key={a.artist_user_id} value={a.artist_user_id}>{a.artist_name}{a.is_ovoxi ? ' (as OVOXI)' : ''}</option>
                  ))}
                </select>
              </label>
            )}
            <button
              onClick={fetchTracks}
              className="text-sm text-slate-400 hover:text-white transition-colors flex items-center gap-1.5"
            >
              <RefreshCw size={14} />
              Refresh
            </button>
            <button
              type="button"
              onClick={onUpload}
              className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(180,79,212,0.6)]"
            >
              {acting ? `+ Upload for ${acting.artist_name}` : '+ Upload Track'}
            </button>
            <SignOutButton>
              <button className="text-sm text-slate-400 hover:text-white transition-colors">
                Sign Out
              </button>
            </SignOutButton>
          </div>
        </div>

        {/* Oct 26: uploads are allowed before approval and held until then. */}
        {isSignedIn && !acting && !uploaderOnly && !['artist', 'admin'].includes(user?.publicMetadata?.role) && (
          <div className="mb-6 rounded-xl border border-amber-400/35 bg-amber-400/[0.06] p-4 text-sm text-amber-100"
            data-testid="vault-pending-approval">
            Your artist account is pending approval. We will email you when you're cleared and able to list your songs in the OVOXI Catalog.
          </div>
        )}

        <div className="mb-6 flex gap-1 overflow-x-auto border-b border-white/10" role="tablist">
          {TABS.map(([key, label]) => (
            <button key={key} type="button" role="tab" aria-selected={shownTab === key} onClick={() => setTab(key)}
              className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm transition-colors ${
                shownTab === key ? 'border-electric text-white' : 'border-transparent text-slate-400 hover:text-white'}`}>
              {label}
            </button>
          ))}
        </div>

        {shownTab === 'wallet' ? (
          <WalletTab getToken={getToken} />
        ) : shownTab === 'uploaders' ? (
          <AuthorizedUploadersTab getToken={getToken} legalName={status?.legal_name} />
        ) : shownTab === 'profile' ? (
          <SyncProfileTab getToken={getToken} tracks={tracks}
            role={user?.publicMetadata?.role} tracksLoaded={tracksLoaded} />
        ) : loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-electric" size={32} />
          </div>
        ) : tracks.length === 0 ? (
          <div className="text-center py-20">
            <Music2 size={48} className="text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400">{acting ? `${acting.artist_name} has no tracks yet.` : 'No tracks yet. Upload your first track to get started.'}</p>
            <button type="button" onClick={onUpload} className="mt-6 inline-block rounded-full bg-gradient-brand px-6 py-2.5 text-sm font-semibold text-white">
              {acting ? `Upload for ${acting.artist_name}` : 'Upload Your First Track'}
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {tracks.map((t) => (
              <div key={t.id} className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-heading text-lg font-medium text-white">{t.track_name}</h3>
                    <p className="text-slate-400 text-sm mt-0.5">{t.genre} · {new Date(t.upload_date).toLocaleDateString()}</p>
                    {t.uploaded_by && (
                      <p className="mt-0.5 text-xs text-[#4FC3F7]" data-testid={`vault-uploaded-by-${t.id}`}>Uploaded by {t.uploaded_by.name}</p>
                    )}
                  </div>
                  <TrackStatusBadge status={t.status} submissionId={t.id} canAppeal={!acting} />
                </div>
                {t.status === 'completed' && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {t.mastered_url && (
                      <a href={t.mastered_url} target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-purple-400/30 bg-purple-400/[0.06] px-3 py-1 text-xs font-medium text-purple-400 hover:bg-purple-400/[0.12] transition-colors">
                        Mastered WAV <ExternalLink size={10} />
                      </a>
                    )}
                    {t.stem_urls && Object.entries(t.stem_urls).map(([stem, url]) => (
                      <a key={stem} href={url} target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-electric/20 bg-electric/[0.06] px-3 py-1 text-xs font-medium text-electric hover:bg-electric/[0.12] transition-colors">
                        {stem.charAt(0).toUpperCase() + stem.slice(1)} <ExternalLink size={10} />
                      </a>
                    ))}
                  </div>
                )}
                {t.legacy ? (
                  <p className="mt-4 border-t border-white/10 pt-3 text-sm text-slate-500">
                    Uploaded before usage options. Re-upload to add it to AI training or sync.
                  </p>
                ) : t.consent && (
                  <TrackSyncPanel track={t} getToken={tokenFn} onUpdated={updateTrack} status={status} acting={acting} />
                )}
                {/* Brief 28 D5: artist only. The backend also refuses this route when acting. */}
                {!acting && !t.legacy && <NotIntendedRemove track={t} getToken={getToken} onUpdated={updateTrack} />}
              </div>
            ))}
          </div>
        )}
      </div>
      <AgreementModal
        open={agreementOpen}
        onClose={() => setAgreementOpen(false)}
        onSigned={() => refreshAgreement()}
        getToken={getToken}
        prefill={status?.prefill}
        previousSigned={status?.previous_signed}
      />
    </div>
  );
};

export default VaultPage;
