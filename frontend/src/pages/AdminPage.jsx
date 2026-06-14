import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, ExternalLink, RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminPage = () => {
  const [password, setPassword] = useState('');
  const [artists, setArtists] = useState(null);
  const [loading, setLoading] = useState(false);
  const [authed, setAuthed] = useState(false);

  const fetchArtists = async (e, pw = password) => {
    if (e) e.preventDefault();
    if (!pw) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/artists`, {
        headers: { 'x-admin-password': pw },
      });
      setArtists(data);
      setAuthed(true);
    } catch (err) {
      if (err.response?.status === 401) {
        toast.error('Incorrect password.');
        setAuthed(false);
      } else {
        toast.error('Failed to load applications.');
      }
    } finally {
      setLoading(false);
    }
  };

  const refresh = () => fetchArtists(null, password);

  return (
    <div className="min-h-screen bg-ink px-6 pt-28 pb-20 lg:pt-36">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-10 flex items-end justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-electric">
              Internal
            </span>
            <h1 className="mt-3 font-heading text-3xl font-semibold text-white lg:text-4xl">
              Artist Applications
            </h1>
          </div>
          {authed && (
            <button
              onClick={refresh}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm text-slate-400 transition-colors hover:border-electric/40 hover:text-white disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
          )}
        </div>

        {/* Password gate */}
        {!authed ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <form
              onSubmit={fetchArtists}
              className="max-w-sm rounded-2xl border border-white/10 bg-white/[0.02] p-8 space-y-5"
            >
              <div className="space-y-2">
                <Label htmlFor="admin-pw" className="text-slate-300">
                  Admin Password
                </Label>
                <Input
                  id="admin-pw"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
                  autoComplete="current-password"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !password}
                className="inline-flex items-center gap-2 rounded-full bg-electric px-6 py-2.5 text-sm font-semibold text-white transition-all hover:shadow-[0_0_20px_rgba(0,102,255,0.5)] disabled:opacity-60"
              >
                {loading && <Loader2 size={14} className="animate-spin" />}
                {loading ? 'Loading…' : 'View Applications'}
              </button>
            </form>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            <p className="mb-5 text-sm text-slate-500">
              {artists?.length ?? 0} application{artists?.length !== 1 ? 's' : ''}
            </p>

            {artists?.length === 0 ? (
              <p className="text-slate-500">No applications yet.</p>
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-white/10">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-white/10 bg-white/[0.02]">
                      {['Name', 'Email', 'Spotify', 'Genre', 'Date Submitted', 'Tracks', 'Files'].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 whitespace-nowrap"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {artists.map((a, i) => (
                      <tr
                        key={a.id}
                        className={`border-b border-white/5 transition-colors hover:bg-white/[0.03] ${
                          i % 2 === 0 ? '' : 'bg-white/[0.01]'
                        }`}
                      >
                        <td className="px-4 py-3 font-medium text-white whitespace-nowrap">
                          {a.name}
                        </td>
                        <td className="px-4 py-3 text-slate-300">{a.email}</td>
                        <td className="px-4 py-3">
                          <a
                            href={a.spotify_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-electric hover:underline"
                          >
                            Spotify <ExternalLink size={11} />
                          </a>
                        </td>
                        <td className="px-4 py-3 text-slate-300 whitespace-nowrap">
                          {a.genre}
                        </td>
                        <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                          {new Date(a.created_at).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </td>
                        <td className="px-4 py-3 text-center text-slate-300">
                          {a.tracks?.length ?? 0}
                        </td>
                        <td className="px-4 py-3">
                          {a.tracks?.length > 0 ? (
                            <div className="flex flex-col gap-1">
                              {a.tracks.map((t) => (
                                <a
                                  key={t.id}
                                  href={t.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-cyan hover:underline whitespace-nowrap"
                                >
                                  {t.title} <ExternalLink size={11} />
                                </a>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default AdminPage;
