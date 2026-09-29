import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { publicApi } from './api';

// Waveform bars from the backend (never straight from R2; see PRD-03 6.3).
const cache = new Map();

const BAR_SLOT_PX = 4;   // 2px bar + 2px gap: the bar count follows the available width

const Waveform = ({ track, progress = 0, bars: maxBars = 90, height = 40, onSeek }) => {
  const { getToken, isSignedIn } = useAuth();
  const [peaks, setPeaks] = useState(cache.get(track.id) || null);
  const boxRef = useRef(null);
  const [bars, setBars] = useState(Math.min(maxBars, 40));

  // Fit the number of bars to the width, so narrow layouts never squeeze
  // bars to zero width (the gaps alone would fill the space).
  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const fit = () => setBars(Math.max(12, Math.min(maxBars, Math.floor(el.clientWidth / BAR_SLOT_PX))));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [maxBars]);

  useEffect(() => {
    if (!track.has_waveform || cache.has(track.id)) return undefined;
    let alive = true;
    publicApi.waveform(track.id, getToken, isSignedIn)
      .then((d) => { cache.set(track.id, d.peaks); if (alive) setPeaks(d.peaks); })
      .catch(() => { cache.set(track.id, []); if (alive) setPeaks([]); });
    return () => { alive = false; };
  }, [track.id, track.has_waveform, getToken, isSignedIn]);

  const values = [];
  if (peaks && peaks.length) {
    const step = peaks.length / bars;
    for (let i = 0; i < bars; i++) {
      const slice = peaks.slice(Math.floor(i * step), Math.max(Math.floor((i + 1) * step), Math.floor(i * step) + 1));
      values.push(Math.max(...slice));
    }
  } else {
    for (let i = 0; i < bars; i++) values.push(0.15);
  }

  const click = (e) => {
    if (!onSeek) return;
    const rect = e.currentTarget.getBoundingClientRect();
    onSeek((e.clientX - rect.left) / rect.width);
  };

  return (
    <div
      ref={boxRef}
      role="slider"
      aria-label={`Seek ${track.track_name}`}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(progress * 100)}
      tabIndex={-1}
      onClick={click}
      className="flex w-full cursor-pointer items-center gap-[2px]"
      style={{ height }}
    >
      {values.map((v, i) => (
        <span
          key={i}
          className={`block flex-1 rounded-[1px] ${i / bars < progress ? 'bg-cyan' : 'bg-slate-700'}`}
          style={{ height: `${Math.max(8, Math.round(v * 100))}%` }}
        />
      ))}
    </div>
  );
};

export default Waveform;
