import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { toast } from 'sonner';
import { publicApi, errorMessage } from './api';

// One audio element for the whole page (PRD-03 6.1: one persistent player).
// Preview links are short-lived (5 minutes), so a new one is requested each
// time a track starts, and once more if the link has expired mid-session.

const PlayerContext = createContext(null);

export const usePlayer = () => useContext(PlayerContext);

export const PlayerProvider = ({ children }) => {
  const { getToken, isSignedIn } = useAuth();
  const audioRef = useRef(null);
  const retried = useRef(false);
  const [track, setTrack] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [loading, setLoading] = useState(false);

  const loadAndPlay = useCallback(async (t, startAt = 0) => {
    const audio = audioRef.current;
    setLoading(true);
    try {
      const { url } = await publicApi.preview(t.id, getToken, isSignedIn);
      audio.src = url;
      audio.currentTime = startAt;
      await audio.play();
    } catch (err) {
      if (err?.name !== 'AbortError') toast.error(errorMessage(err, 'Preview unavailable. Please try again.'));
    } finally {
      setLoading(false);
    }
  }, [getToken, isSignedIn]);

  const toggle = useCallback((t) => {
    const audio = audioRef.current;
    if (track && track.id === t.id) {
      if (audio.paused) audio.play().catch(() => {}); else audio.pause();
      return;
    }
    retried.current = false;
    setTrack(t);
    setTime(0);
    setDuration(t.duration_s || 0);
    loadAndPlay(t, 0);
  }, [track, loadAndPlay]);

  const seek = useCallback((t, fraction) => {
    const audio = audioRef.current;
    if (!track || track.id !== t.id) { toggle(t); return; }
    const total = audio.duration || duration;
    if (total) audio.currentTime = Math.max(0, Math.min(total, fraction * total));
  }, [track, toggle, duration]);

  useEffect(() => {
    const audio = audioRef.current;
    const onTime = () => setTime(audio.currentTime);
    const onMeta = () => audio.duration && setDuration(audio.duration);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onError = () => {
      // Most likely an expired 5-minute link: ask for a fresh one once.
      if (track && !retried.current) {
        retried.current = true;
        loadAndPlay(track, audio.currentTime || 0);
      } else {
        setPlaying(false);
      }
    };
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('ended', onPause);
    audio.addEventListener('error', onError);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('ended', onPause);
      audio.removeEventListener('error', onError);
    };
  }, [track, loadAndPlay]);

  const value = { track, playing, time, duration, loading, toggle, seek };
  return (
    <PlayerContext.Provider value={value}>
      {/* controlsList/onContextMenu: no download button (PRD-03 6.3). */}
      <audio ref={audioRef} preload="none" controlsList="nodownload" onContextMenu={(e) => e.preventDefault()} />
      {children}
    </PlayerContext.Provider>
  );
};

export const fmtTime = (s) => {
  if (!Number.isFinite(s) || s < 0) return '0:00';
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
};
