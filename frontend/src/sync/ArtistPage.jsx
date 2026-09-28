import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { Loader2 } from 'lucide-react';
import { publicApi } from './api';
import { PlayerProvider } from './PlayerContext';
import PlayerBar from './PlayerBar';
import TrackRow from './TrackRow';
import { Avatar, NotFound, VisibilityBanner } from './PublicPageParts';

// Public artist page /artist/:slug (PRD-03 6.2, decisions 17 and 18).

const ArtistPageInner = () => {
  const { slug } = useParams();
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const [state, setState] = useState({ loading: true, data: null, missing: false });

  useEffect(() => {
    if (!isLoaded) return undefined;
    let alive = true;
    setState({ loading: true, data: null, missing: false });
    publicApi.artist(slug, getToken, isSignedIn)
      .then((data) => alive && setState({ loading: false, data, missing: false }))
      .catch(() => alive && setState({ loading: false, data: null, missing: true }));
    return () => { alive = false; };
  }, [slug, getToken, isSignedIn, isLoaded]);

  if (state.loading) return <div className="flex min-h-[60vh] justify-center pt-40"><Loader2 className="animate-spin text-electric" size={32} /></div>;
  if (state.missing) return <NotFound />;

  const { profile, tracks, viewer } = state.data;
  return (
    <div className="min-h-screen bg-ink pb-28 pt-20" data-testid="artist-page">
      <VisibilityBanner viewer={viewer} />
      <div className="mx-auto max-w-5xl px-4">
        <div className="flex flex-wrap items-center gap-6 border-b border-white/10 py-8">
          <Avatar profile={profile} />
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-[0.2em] text-cyan">Artist</p>
            <h1 className="mt-1.5 font-heading text-4xl font-extrabold text-white md:text-5xl">{profile.display_name}</h1>
            {profile.location && <p className="mt-1 text-sm text-slate-400">{profile.location}</p>}
            {profile.bio && <p className="mt-3 max-w-2xl whitespace-pre-line text-[15px] leading-relaxed text-slate-300">{profile.bio}</p>}
            <div className="mt-4 flex flex-wrap gap-2">
              {profile.spotify_url && <a href={profile.spotify_url} target="_blank" rel="noopener noreferrer nofollow" className="rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-slate-300 hover:text-white">Spotify ↗</a>}
              {profile.instagram_url && <a href={profile.instagram_url} target="_blank" rel="noopener noreferrer nofollow" className="rounded-full border border-white/10 px-3.5 py-1.5 text-[13px] text-slate-300 hover:text-white">Instagram ↗</a>}
              {viewer.is_owner && (
                <Link to="/vault?tab=profile" className="rounded-full bg-gradient-brand px-4 py-1.5 text-[13px] font-semibold text-white" data-testid="edit-profile">
                  Edit profile
                </Link>
              )}
            </div>
            {viewer.is_admin && profile.hidden_by_admin && (
              <p className="mt-3 text-xs text-amber-300">Photo and bio are hidden from the public by an admin.</p>
            )}
          </div>
        </div>
        <h2 className="mb-3 mt-7 font-heading text-xl font-semibold text-white">Tracks</h2>
        {tracks.length === 0 ? (
          <p className="text-sm text-slate-400" data-testid="no-tracks">
            No tracks listed yet. Add tracks to your sync profile in your Vault.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {tracks.map((t) => <TrackRow key={t.id} track={t} showArtist={false} />)}
          </div>
        )}
      </div>
      <PlayerBar />
    </div>
  );
};

const ArtistPage = () => <PlayerProvider><ArtistPageInner /></PlayerProvider>;
export default ArtistPage;
