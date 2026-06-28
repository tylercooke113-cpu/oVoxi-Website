import React, { useEffect, useState, useCallback } from 'react';
import { useUser, useAuth, SignOutButton } from '@clerk/clerk-react';
import { Navigate } from 'react-router-dom';
import axios from 'axios';
import { Loader2, Music2, ExternalLink, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';

const API = 'https://ovoxi-website-production.up.railway.app/api';

const STATUS_LABELS = {
  pending: 'Queued',
  uploaded: 'Uploaded',
  mastering: 'Mastering...',
  processing: 'Processing stems...',
  completed: 'Ready',
  failed: 'Failed',
};

const STATUS_COLORS = {
  pending: 'text-slate-400',
  uploaded: 'text-blue-400',
  mastering: 'text-purple-400',
  processing: 'text-yellow-400',
  completed: 'text-green-400',
  failed: 'text-red-400',
};

const VaultPage = () => {
  const { isLoaded, isSignedIn, user } = useUser();
  const { getToken } = useAuth();
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchTracks = useCallback(async () => {
    if (!isLoaded || !isSignedIn) return;
    setLoading(true);
    try {
      const token = await getToken();
      const res = await axios.get(`${API}/vault/tracks`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTracks(res.data);
    } catch (err) {
      console.error('Failed to fetch tracks', err);
    } finally {
      setLoading(false);
    }
  }, [isLoaded, isSignedIn, getToken]);

  useEffect(() => {
    fetchTracks();
  }, [fetchTracks]);

  if (!isLoaded) return null;
  if (!isSignedIn) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-ink pt-24 pb-16 px-6">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center justify-between mb-10">
          <div>
            <h1 className="font-heading text-3xl font-semibold text-white">
              My Vault
            </h1>
            <p className="text-slate-400 text-sm mt-1">{user?.firstName} {user?.lastName}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchTracks}
              className="text-sm text-slate-400 hover:text-white transition-colors flex items-center gap-1.5"
            >
              <RefreshCw size={14} />
              Refresh
            </button>
            <Link
              to="/upload"
              className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(180,79,212,0.6)]"
            >
              + Upload Track
            </Link>
            <SignOutButton>
              <button className="text-sm text-slate-400 hover:text-white transition-colors">
                Sign Out
              </button>
            </SignOutButton>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="animate-spin text-electric" size={32} />
          </div>
        ) : tracks.length === 0 ? (
          <div className="text-center py-20">
            <Music2 size={48} className="text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400">No tracks yet. Upload your first track to get started.</p>
            <Link to="/upload" className="mt-6 inline-block rounded-full bg-gradient-brand px-6 py-2.5 text-sm font-semibold text-white">
              Upload Your First Track
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {tracks.map((t) => (
              <div key={t.id} className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-heading text-lg font-medium text-white">{t.track_name}</h3>
                    <p className="text-slate-400 text-sm mt-0.5">{t.genre} · {new Date(t.upload_date).toLocaleDateString()}</p>
                  </div>
                  <span className={`text-sm font-medium ${STATUS_COLORS[t.status] ?? 'text-slate-400'}`}>
                    {STATUS_LABELS[t.status] ?? t.status}
                  </span>
                </div>
                {t.status === 'completed' && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {t.mastered_url && (
                      <a href={t.mastered_url} target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-purple-400/30 bg-purple-400/[0.06] px-3 py-1 text-xs font-medium text-purple-400 hover:bg-purple-400/[0.12] transition-colors">
                        Mastered WAV <ExternalLink size={10} />
                      </a>
                    )}
                    {t.stem_urls && Object.entries(t.stem_urls).map(([stem, url]) => (
                      <a key={stem} href={url} target="_blank" rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-electric/20 bg-electric/[0.06] px-3 py-1 text-xs font-medium text-electric hover:bg-electric/[0.12] transition-colors">
                        {stem.charAt(0).toUpperCase() + stem.slice(1)} <ExternalLink size={10} />
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default VaultPage;
