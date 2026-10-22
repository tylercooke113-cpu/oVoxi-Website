import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { fmtTime, usePlayer } from './PlayerContext';
import { PlayButton } from './TrackRow';
import { safeNext } from '../lib/safeNext';

const PlayerBar = () => {
  const { track, time, duration, seek, excerpt } = usePlayer();
  const location = useLocation();
  if (!track) return null;
  const pct = duration ? Math.min(100, (time / duration) * 100) : 0;
  const click = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    seek(track, (e.clientX - rect.left) / rect.width);
  };
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-[#1C1C21] bg-[#0A0A0C]"
      data-testid="player-bar">
      {excerpt && (
        <p className="px-4 pt-2 text-xs text-slate-400" data-testid="excerpt-note-bar">
          60-second preview.{' '}
          <Link
            to={`/login?next=${encodeURIComponent(safeNext(location.pathname + location.search))}`}
            className="text-cyan hover:underline">
            Sign in to hear the full song.
          </Link>
        </p>
      )}
      <div className="flex items-center gap-3.5 px-4 py-3">
        <PlayButton track={track} size={36} />
        <div className="min-w-0 max-w-[40%]">
          <p className="truncate text-sm text-white">{track.track_name}</p>
          <p className="truncate text-xs text-slate-400">{track.artist_display_name}</p>
        </div>
        <div className="relative h-1 flex-1 cursor-pointer rounded bg-white/10" onClick={click} role="presentation">
          <div className="absolute inset-y-0 left-0 rounded bg-cyan" style={{ width: `${pct}%` }} />
        </div>
        <span className="whitespace-nowrap text-xs text-slate-400">{fmtTime(time)} / {fmtTime(duration)}</span>
      </div>
    </div>
  );
};

export default PlayerBar;
