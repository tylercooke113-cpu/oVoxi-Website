import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { Loader2, SlidersHorizontal, X } from 'lucide-react';
import { publicApi } from './api';
import { PlayerProvider } from './PlayerContext';
import PlayerBar from './PlayerBar';
import TrackRow from './TrackRow';
import { NotFound } from './PublicPageParts';
import { BPM_MAX, BPM_MIN, MOODS } from './constants';

// The sync library /sync (PRD-03 6.1, decisions 21 and 22). All filters live in
// the address bar so a filtered view can be shared.

const GENRES = ['Hip-Hop', 'R&B', 'Afrobeats', 'Trap', 'Soul', 'Pop',
  'Electronic', 'Latin', 'Reggaeton', 'Afropop', 'Other'];
const LENGTHS = [['', 'Any'], ['0-60', 'Under 1:00'], ['60-180', '1 to 3 min'], ['180-900', '3 min +']];
const VOCALS = [['', 'Any'], ['vocal', 'Vocal'], ['instrumental', 'Instrumental']];
const PARAM_KEYS = ['genre', 'mood', 'bpm', 'vocals', 'length', 'sort'];

const listOf = (v) => (v ? v.split(',').filter(Boolean) : []);

const Chip = ({ on, children, onClick }) => (
  <button type="button" aria-pressed={on} onClick={onClick}
    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
      on ? 'border-electric-light bg-electric/20 text-white' : 'border-white/10 text-slate-300 hover:text-white'}`}>
    {children}
  </button>
);

const Group = ({ title, children }) => (
  <div className="border-b border-white/10 py-3.5">
    <h4 className="mb-2.5 text-xs font-medium uppercase tracking-[0.14em] text-slate-500">{title}</h4>
    {children}
  </div>
);

const FilterRail = ({ params, set, onClear }) => {
  const [bmin, bmax] = (params.get('bpm') || '-').split('-');
  const [lo, setLo] = useState(bmin || '');
  const [hi, setHi] = useState(bmax || '');
  useEffect(() => { setLo(bmin || ''); setHi(bmax || ''); }, [bmin, bmax]);

  const toggle = (key, value) => {
    const cur = listOf(params.get(key));
    set(key, (cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value]).join(','));
  };
  const commitBpm = () => {
    const a = lo === '' ? '' : Math.max(BPM_MIN, Math.min(BPM_MAX, Number(lo)));
    const b = hi === '' ? '' : Math.max(BPM_MIN, Math.min(BPM_MAX, Number(hi)));
    if (a !== '' && b !== '' && a > b) { set('bpm', `${b}-${a}`); return; }
    set('bpm', a === '' && b === '' ? '' : `${a}-${b}`);
  };
  const bpmField = (value, setter, label) => (
    <input inputMode="numeric" aria-label={label} value={value} placeholder={label === 'Minimum BPM' ? String(BPM_MIN) : String(BPM_MAX)}
      onChange={(e) => setter(e.target.value.replace(/\D/g, '').slice(0, 3))}
      onBlur={commitBpm} onKeyDown={(e) => e.key === 'Enter' && commitBpm()}
      className="w-[70px] rounded-md border border-white/10 bg-ink px-2 py-1.5 text-sm text-white placeholder:text-slate-600" />
  );

  return (
    <>
      <Group title="Genre">
        <div className="flex flex-wrap gap-1.5">
          {GENRES.map((g) => <Chip key={g} on={listOf(params.get('genre')).includes(g)} onClick={() => toggle('genre', g)}>{g}</Chip>)}
        </div>
      </Group>
      <Group title="Mood">
        <div className="flex flex-wrap gap-1.5">
          {MOODS.map((m) => <Chip key={m} on={listOf(params.get('mood')).includes(m)} onClick={() => toggle('mood', m)}>{m}</Chip>)}
        </div>
      </Group>
      <Group title="BPM">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          {bpmField(lo, setLo, 'Minimum BPM')} to {bpmField(hi, setHi, 'Maximum BPM')}
        </div>
      </Group>
      <Group title="Vocals">
        <div className="flex flex-wrap gap-1.5">
          {VOCALS.map(([v, l]) => <Chip key={l} on={(params.get('vocals') || '') === v} onClick={() => set('vocals', v)}>{l}</Chip>)}
        </div>
      </Group>
      <Group title="Length">
        <div className="flex flex-wrap gap-1.5">
          {LENGTHS.map(([v, l]) => <Chip key={l} on={(params.get('length') || '') === v} onClick={() => set('length', v)}>{l}</Chip>)}
        </div>
      </Group>
      <button type="button" onClick={onClear} className="py-3 text-sm text-cyan">Clear all filters</button>
    </>
  );
};

const LibraryInner = () => {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const [params, setParams] = useSearchParams();
  const [drawer, setDrawer] = useState(false);
  const [state, setState] = useState({ loading: true, missing: false, tracks: [], cursor: null, total: null, sort: 'newest', viewer: null, error: false });
  const [loadingMore, setLoadingMore] = useState(false);

  const query = Object.fromEntries(PARAM_KEYS.map((k) => [k, params.get(k)]).filter(([, v]) => v));
  const queryKey = JSON.stringify(query);

  const set = useCallback((key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  }, [params, setParams]);

  const clearAll = () => setParams(new URLSearchParams(params.get('sort') ? { sort: params.get('sort') } : {}), { replace: true });

  useEffect(() => {
    if (!isLoaded) return undefined;
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: false }));
    publicApi.library(JSON.parse(queryKey), getToken, isSignedIn)
      .then((d) => alive && setState({ loading: false, missing: false, error: false, tracks: d.tracks, cursor: d.next_cursor,
        total: d.total, sort: d.sort, viewer: d.viewer }))
      .catch((err) => alive && setState((s) => ({ ...s, loading: false,
        missing: err?.response?.status === 404, error: err?.response?.status !== 404 })));
    return () => { alive = false; };
  }, [queryKey, getToken, isSignedIn, isLoaded]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const d = await publicApi.library({ ...query, sort: state.sort, cursor: state.cursor }, getToken, isSignedIn);
      setState((s) => ({ ...s, tracks: [...s.tracks, ...d.tracks], cursor: d.next_cursor }));
    } catch {
      setState((s) => ({ ...s, error: true }));
    } finally {
      setLoadingMore(false);
    }
  };

  if (state.missing) return <NotFound />;

  const active = [
    ...listOf(params.get('genre')).map((v) => ['genre', v, v]),
    ...listOf(params.get('mood')).map((v) => ['mood', v, v]),
    ...(params.get('bpm') ? [['bpm', null, `${params.get('bpm').replace('-', ' to ')} BPM`]] : []),
    ...(params.get('vocals') ? [['vocals', null, params.get('vocals') === 'vocal' ? 'Vocal' : 'Instrumental']] : []),
    ...(params.get('length') ? [['length', null, LENGTHS.find(([v]) => v === params.get('length'))?.[1] || 'Length']] : []),
  ];
  const removePill = ([key, value]) => {
    if (value === null) { set(key, ''); return; }
    set(key, listOf(params.get(key)).filter((v) => v !== value).join(','));
  };

  return (
    <div className="min-h-screen bg-ink pb-28 pt-20" data-testid="library-page">
      {state.viewer && !state.viewer.public && (
        <div className="mx-auto mt-6 max-w-6xl px-4">
          <div className="rounded-xl border border-cyan/30 bg-cyan/[0.06] px-4 py-2.5 text-[13px] text-sky-200" data-testid="visibility-banner">
            Admin preview. The library is only visible to admins until it's switched on.
          </div>
        </div>
      )}
      <div className="mx-auto max-w-6xl px-4 pt-6">
        <p className="text-xs uppercase tracking-[0.2em] text-cyan">oVoxi sync library</p>
        <h1 className="mt-1.5 font-heading text-4xl font-extrabold text-white md:text-5xl">Discover our royalty-free music for videos</h1>
        <p className="mb-6 mt-2 text-slate-400">All genres and sounds. Cleared for sync.</p>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[250px_1fr]">
          <aside className="hidden lg:block" data-testid="filter-rail">
            <FilterRail params={params} set={set} onClear={clearAll} />
          </aside>

          {drawer && (
            <div className="fixed inset-0 z-50 overflow-y-auto bg-[#0A0A0C] p-5 lg:hidden" role="dialog" aria-label="Filters">
              <button type="button" onClick={() => setDrawer(false)}
                className="mb-2 inline-flex items-center gap-1 rounded-full border border-white/10 px-4 py-1.5 text-sm text-white">
                <X size={14} /> Done
              </button>
              <FilterRail params={params} set={set} onClear={clearAll} />
            </div>
          )}

          <main>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2.5">
              <span className="text-sm text-slate-400" data-testid="result-count">
                {state.total != null ? `${state.total} track${state.total === 1 ? '' : 's'}` : ''}
              </span>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => setDrawer(true)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-3.5 py-1.5 text-sm text-white lg:hidden">
                  <SlidersHorizontal size={14} /> Filters
                </button>
                <label className="flex items-center gap-2 text-sm text-slate-400">
                  Sort
                  <select value={params.get('sort') || state.sort} onChange={(e) => set('sort', e.target.value)}
                    className="rounded-md border border-white/10 bg-ink px-2 py-1.5 text-white" data-testid="sort">
                    <option value="newest">Newest</option>
                    <option value="popular">Popular</option>
                  </select>
                </label>
              </div>
            </div>

            {active.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {active.map((p) => (
                  <button key={`${p[0]}-${p[2]}`} type="button" onClick={() => removePill(p)}
                    className="inline-flex items-center gap-1 rounded-full border border-electric/50 px-2.5 py-0.5 text-xs text-purple-200">
                    {p[2]} <X size={11} />
                  </button>
                ))}
              </div>
            )}

            {state.error && <p className="mb-3 text-sm text-red-400">Something went wrong loading tracks. Please try again.</p>}

            {state.loading ? (
              <div className="flex justify-center py-16"><Loader2 className="animate-spin text-electric" size={28} /></div>
            ) : state.tracks.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center text-slate-400" data-testid="empty">
                No tracks match these filters.{' '}
                {active.length > 0 && <button type="button" onClick={clearAll} className="text-cyan">Clear filters</button>}
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {state.tracks.map((t) => <TrackRow key={t.id} track={t} />)}
              </div>
            )}

            {state.cursor && !state.loading && (
              <button type="button" onClick={loadMore} disabled={loadingMore} data-testid="load-more"
                className="mx-auto mt-5 block rounded-full border border-white/10 px-6 py-2.5 text-white disabled:opacity-50">
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            )}
          </main>
        </div>
      </div>
      <PlayerBar />
    </div>
  );
};

const LibraryPage = () => <PlayerProvider><LibraryInner /></PlayerProvider>;
export default LibraryPage;
