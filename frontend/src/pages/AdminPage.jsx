import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, ExternalLink, RefreshCw, CheckCircle2, Clock, AlertCircle, Zap } from 'lucide-react';
import { motion } from 'framer-motion';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

const API = `https://ovoxi-website-production.up.railway.app/api`;

const STEM_LABELS = { vocals: 'Vocals', drums: 'Drums', bass: 'Bass', other: 'Other' };

const StatusBadge = ({ status }) => {
  const map = {
    pending:    { icon: Clock,        color: 'text-slate-400',  label: 'Pending' },
    uploaded:   { icon: Clock,        color: 'text-blue-400',   label: 'Uploaded' },
    processing: { icon: Zap,          color: 'text-yellow-400', label: 'Processing' },
    completed:  { icon: CheckCircle2, color: 'text-green-400',  label: 'Completed' },
    failed:     { icon: AlertCircle,  color: 'text-red-400',    label: 'Failed' },
  };
  const { icon: Icon, color, label } = map[status] || map.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${color}`}>
      <Icon size={12} />
      {label}
    </span>
  );
};

const AdminPage = () => {
  const [password, setPassword] = useState('');
  const [tab, setTab] = useState('submissions'); // 'submissions' | 'applications' | 'messages'
  const [artists, setArtists] = useState(null);
  const [submissions, setSubmissions] = useState(null);
  const [messages, setMessages] = useState(null);
  const [loading, setLoading] = useState(false);
  const [authed, setAuthed] = useState(false);

  const fetchAll = async (pw = password) => {
    if (!pw) return;
    setLoading(true);
    try {
      const headers = { 'x-admin-password': pw };
      const [artRes, subRes, msgRes] = await Promise.all([
        axios.get(`${API}/artists`, { headers }),
        axios.get(`${API}/submissions`, { headers }),
        axios.get(`${API}/contact`, { headers }),
      ]);
      setArtists(artRes.data);
      setSubmissions(subRes.data);
      setMessages(msgRes.data);
      setAuthed(true);
    } catch (err) {
      if (err.response?.status === 401) {
        toast.error('Incorrect password.');
        setAuthed(false);
      } else {
        toast.error('Failed to load data.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (e) => {
    e.preventDefault();
    fetchAll();
  };

  const refresh = () => fetchAll(password);

  return (
    <div className="min-h-screen bg-ink px-6 pt-28 pb-20 lg:pt-36">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-10 flex items-end justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.25em] text-electric">
              Catalog
            </span>
            <h1 className="mt-3 font-heading text-3xl font-semibold text-white lg:text-4xl">
              My Vault
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
              onSubmit={handleLogin}
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
                {loading ? 'Loading…' : 'View Panel'}
              </button>
            </form>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            {/* Tabs */}
            <div className="mb-8 flex gap-1 rounded-full border border-white/10 bg-white/[0.02] p-1 w-fit">
              {[
                { key: 'submissions', label: `Submissions (${submissions?.length ?? 0})` },
                { key: 'applications', label: `Applications (${artists?.length ?? 0})` },
                { key: 'messages', label: `Messages (${messages?.length ?? 0})` },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`rounded-full px-5 py-2 text-sm font-medium transition-all ${
                    tab === key
                      ? 'bg-electric text-white shadow-[0_0_16px_rgba(0,102,255,0.4)]'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Submissions tab */}
            {tab === 'submissions' && (
              <>
                {submissions?.length === 0 ? (
                  <p className="text-slate-500">No submissions yet.</p>
                ) : (
                  <div className="overflow-x-auto rounded-2xl border border-white/10">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-white/10 bg-white/[0.02]">
                          {['Artist', 'Track', 'Genre', 'Date', 'Status', 'Stems'].map((h) => (
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
                        {submissions.map((s, i) => (
                          <tr
                            key={s.id}
                            className={`border-b border-white/5 transition-colors hover:bg-white/[0.03] ${
                              i % 2 === 0 ? '' : 'bg-white/[0.01]'
                            }`}
                          >
                            <td className="px-4 py-3 font-medium text-white whitespace-nowrap">
                              {s.artist_name}
                            </td>
                            <td className="px-4 py-3 text-slate-300 whitespace-nowrap">
                              {s.track_name}
                            </td>
                            <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                              {s.genre}
                            </td>
                            <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                              {new Date(s.upload_date).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <StatusBadge status={s.status} />
                              {s.status === 'failed' && s.error && (
                                <p className="mt-1 text-xs text-red-400/70 max-w-[200px] break-words">
                                  {s.error}
                                </p>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {s.status === 'completed' && Object.keys(s.stem_urls ?? {}).length > 0 ? (
                                <div className="flex flex-col gap-1">
                                  {Object.entries(s.stem_urls).map(([stem, url]) => (
                                    <a
                                      key={stem}
                                      href={url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 rounded-md border border-electric/20 bg-electric/[0.06] px-2 py-0.5 text-xs font-medium text-electric whitespace-nowrap hover:bg-electric/[0.12] transition-colors"
                                    >
                                      {STEM_LABELS[stem] ?? stem}
                                      <ExternalLink size={10} />
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
              </>
            )}

            {/* Messages tab */}
            {tab === 'messages' && (
              <>
                {messages?.length === 0 ? (
                  <p className="text-slate-500">No messages yet.</p>
                ) : (
                  <div className="overflow-x-auto rounded-2xl border border-white/10">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-white/10 bg-white/[0.02]">
                          {['Name', 'Email', 'Interest', 'Date', 'Message'].map((h) => (
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
                        {messages?.map((m, i) => (
                          <tr
                            key={m.id}
                            className={`border-b border-white/5 transition-colors hover:bg-white/[0.03] ${
                              i % 2 === 0 ? '' : 'bg-white/[0.01]'
                            }`}
                          >
                            <td className="px-4 py-3 font-medium text-white whitespace-nowrap">
                              {m.name}
                              {m.company && (
                                <span className="ml-1.5 text-xs text-slate-500">({m.company})</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-slate-300 whitespace-nowrap">{m.email}</td>
                            <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                              {m.interest ?? '—'}
                            </td>
                            <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                              {new Date(m.created_at).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              })}
                            </td>
                            <td className="px-4 py-3 text-slate-300 max-w-xs">
                              <p className="whitespace-pre-wrap break-words">{m.message}</p>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}

            {/* Applications tab */}
            {tab === 'applications' && (
              <>
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
              </>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default AdminPage;
