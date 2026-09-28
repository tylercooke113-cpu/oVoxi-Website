import React from 'react';
import { fmtTime, usePlayer } from './PlayerContext';
import { PlayButton } from './TrackRow';

const PlayerBar = () => {
  const { track, time, duration, seek } = usePlayer();
  if (!track) return null;
  const pct = duration ? Math.min(100, (time / duration) * 100) : 0;
  const click = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    seek(track, (e.clientX - rect.left) / rect.width);
  };
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 flex items-center gap-3.5 border-t border-[#1C1C21] bg-[#0A0A0C] px-4 py-3"
      data-testid="player-bar">
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
  );
};

export default PlayerBar;
