import React from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Pause, Play } from 'lucide-react';
import Waveform from './Waveform';
import { fmtTime, usePlayer } from './PlayerContext';

// One listed track (PRD-03 6.1 row). Checkout arrives in Phase 6.

export const LicenseButton = () => (
  <button type="button" disabled title="Licensing opens soon"
    className="cursor-not-allowed whitespace-nowrap rounded-full border border-white/10 px-3 py-2 text-xs text-slate-500 sm:px-4">
    <span className="sm:hidden">License</span>
    <span className="hidden sm:inline">License · coming soon</span>
  </button>
);

export const PlayButton = ({ track, size = 40 }) => {
  const { track: current, playing, loading, toggle } = usePlayer();
  const isCurrent = current && current.id === track.id;
  const disabled = !track.has_preview;
  return (
    <button type="button" onClick={() => toggle(track)} disabled={disabled}
      aria-label={isCurrent && playing ? `Pause ${track.track_name}` : `Play ${track.track_name}`}
      className="flex flex-none items-center justify-center rounded-full bg-gradient-brand text-white transition-opacity disabled:opacity-40"
      style={{ width: size, height: size }}>
      {isCurrent && loading ? <Loader2 size={16} className="animate-spin" />
        : isCurrent && playing ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
    </button>
  );
};

export const Tags = ({ track }) => (
  <div className="mt-1.5 flex flex-wrap gap-1.5">
    {[track.genre, ...(track.moods || [])].filter(Boolean).map((t) => (
      <span key={t} className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-300">{t}</span>
    ))}
  </div>
);

const TrackRow = ({ track, showArtist = true }) => {
  const { track: current, time, duration, seek } = usePlayer();
  const isCurrent = current && current.id === track.id;
  const progress = isCurrent && duration ? time / duration : 0;
  return (
    <div className="grid grid-cols-[44px_1fr_auto] items-center gap-3.5 rounded-2xl border border-white/10 bg-white/[0.015] px-3.5 py-3 md:grid-cols-[44px_220px_1fr_150px_auto]"
      data-testid={`track-row-${track.id}`}>
      <PlayButton track={track} />
      <div className="min-w-0">
        <Link to={`/sync/track/${track.id}`} className="block truncate text-[15px] font-medium text-white hover:underline">
          {track.track_name}
        </Link>
        {showArtist && (
          track.artist_slug
            ? <Link to={`/artist/${track.artist_slug}`} className="text-[13px] text-slate-400 hover:text-white">{track.artist_display_name}</Link>
            : <span className="text-[13px] text-slate-400">{track.artist_display_name}</span>
        )}
        <Tags track={track} />
      </div>
      <div className="hidden md:block">
        <Waveform track={track} progress={progress} onSeek={(f) => seek(track, f)} />
      </div>
      <div className="hidden text-right text-[13px] leading-relaxed text-slate-400 md:block">
        {track.bpm != null && <>{track.bpm} BPM</>}{track.key && <> · {track.key}</>}<br />
        {fmtTime(track.duration_s)}{track.vocals && <> · {track.vocals === 'vocal' ? 'Vocal' : 'Instrumental'}</>}
      </div>
      <LicenseButton />
    </div>
  );
};

export default TrackRow;
