import React, { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { Loader2 } from 'lucide-react';
import { publicApi } from './api';
import { PlayerProvider, fmtTime, usePlayer } from './PlayerContext';
import PlayerBar from './PlayerBar';
import Waveform from './Waveform';
import { PlayButton, Tags } from './TrackRow';
import LicenseButton from './LicenseButton';
import { Avatar, NotFound, VisibilityBanner } from './PublicPageParts';

// Track share page /sync/track/:id (PRD-03 6; the artist's link to send buyers).

const Fact = ({ label, value }) => (
  <div className="rounded-xl border border-white/10 p-3">
    <span className="block text-[11px] uppercase tracking-[0.12em] text-slate-500">{label}</span>
    <b className="text-base font-medium text-white">{value ?? '-'}</b>
  </div>
);

const TrackSharePageInner = () => {
  const { id } = useParams();
  const [params] = useSearchParams();
  const cancelled = params.get('checkout') === 'cancelled';
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const { track: current, time, duration, seek } = usePlayer();
  const [state, setState] = useState({ loading: true, data: null, missing: false });

  useEffect(() => {
    if (!isLoaded) return undefined;
    let alive = true;
    publicApi.track(id, getToken, isSignedIn)
      .then((data) => alive && setState({ loading: false, data, missing: false }))
      .catch(() => alive && setState({ loading: false, data: null, missing: true }));
    return () => { alive = false; };
  }, [id, getToken, isSignedIn, isLoaded]);

  if (state.loading) return <div className="flex min-h-[60vh] justify-center pt-40"><Loader2 className="animate-spin text-electric" size={32} /></div>;
  if (state.missing) return <NotFound />;

  const { track, artist, listed, viewer } = state.data;
  const isCurrent = current && current.id === track.id;
  const progress = isCurrent && duration ? time / duration : 0;
  return (
    <div className="min-h-screen bg-ink pb-28 pt-20" data-testid="track-page">
      <VisibilityBanner viewer={viewer} />
      <div className="mx-auto max-w-3xl px-4 pt-6">
        {cancelled && (
          <p className="mb-4 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-[13px] text-slate-300" data-testid="checkout-cancelled">
            Checkout cancelled. You weren't charged.
          </p>
        )}
        {!listed && (
          <p className="mb-4 rounded-xl border border-amber-400/30 bg-amber-400/[0.06] px-4 py-2.5 text-[13px] text-amber-100">
            This track isn't live yet. Check its status in your Vault.
          </p>
        )}
        <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-6">
          <p className="text-xs uppercase tracking-[0.2em] text-cyan">Sync license</p>
          <h1 className="mt-1.5 font-heading text-4xl font-extrabold text-white">{track.track_name}</h1>
          <div className="mt-2 flex items-center gap-2.5 text-sm text-slate-400">
            {artist && <Avatar profile={artist} size={28} />}
            {track.artist_slug
              ? <Link to={`/artist/${track.artist_slug}`} className="text-slate-300 hover:text-white">{track.artist_display_name}</Link>
              : <span>{track.artist_display_name}</span>}
          </div>
          <div className="my-5">
            <Waveform track={track} bars={160} height={90} progress={progress} onSeek={(f) => seek(track, f)} />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <PlayButton track={track} size={52} />
            <LicenseButton track={track} />
          </div>
          <div className="my-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Fact label="BPM" value={track.bpm} />
            <Fact label="Key" value={track.key} />
            <Fact label="Length" value={fmtTime(track.duration_s)} />
            <Fact label="Vocals" value={track.vocals === 'vocal' ? 'Vocal' : track.vocals ? 'Instrumental' : null} />
          </div>
          <Tags track={track} />
          <p className="mt-3 text-xs text-slate-500">Preview streams only. Licensed files are delivered after purchase.</p>
        </div>
      </div>
      <PlayerBar />
    </div>
  );
};

const TrackSharePage = () => <PlayerProvider><TrackSharePageInner /></PlayerProvider>;
export default TrackSharePage;
