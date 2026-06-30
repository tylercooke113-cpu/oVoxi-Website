import React, { useState, useRef, useEffect } from 'react';
import { useParams, Navigate, Link } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import axios from 'axios';
import { toast } from 'sonner';
import { Upload, FileText, CheckCircle2, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { BRAND } from '../content';

const API = 'https://ovoxi-website-production.up.railway.app/api';
const ACCEPTED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'];
const MAX_PROOF_BYTES = 20 * 1024 * 1024;

const AppealPage = () => {
  const { submissionId } = useParams();
  const { getToken, isSignedIn, isLoaded } = useAuth();

  const [track, setTrack] = useState(null);
  const [loadingTrack, setLoadingTrack] = useState(true);
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState('');
  const [stage, setStage] = useState('idle'); // idle | uploading | done
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    (async () => {
      try {
        const token = await getToken();
        const { data } = await axios.get(`${API}/vault/tracks`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setTrack(data.find((t) => t.id === submissionId) ?? null);
      } catch {
        setTrack(null);
      } finally {
        setLoadingTrack(false);
      }
    })();
  }, [isLoaded, isSignedIn, submissionId, getToken]);

  if (!isLoaded) return null;
  if (!isSignedIn) return <Navigate to="/login" replace />;

  if (loadingTrack) {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center">
        <Loader2 className="animate-spin text-electric" size={32} />
      </div>
    );
  }

  if (!track || track.status !== 'CONFLICT') {
    return <Navigate to="/vault" replace />;
  }

  const handleFile = (f) => {
    if (!f) return;
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      toast.error('Accepted formats: PDF, JPG, PNG, DOC, DOCX');
      return;
    }
    if (f.size > MAX_PROOF_BYTES) {
      toast.error('File exceeds the 20 MB limit.');
      return;
    }
    setFile(f);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      toast.error('Please attach a proof document.');
      return;
    }
    setStage('uploading');
    setUploadProgress(0);
    try {
      const token = await getToken();

      const { data: presignData } = await axios.post(
        `${API}/appeal/presign`,
        {
          submission_id: submissionId,
          artist_name: track.artist_name,
          track_name: track.track_name,
          filename: file.name,
          message: message.trim() || null,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const { presigned_url, appeal_id, content_type } = presignData;

      await axios.put(presigned_url, file, {
        headers: { 'Content-Type': content_type },
        onUploadProgress: (ev) => {
          if (ev.total) setUploadProgress(Math.round((ev.loaded / ev.total) * 100));
        },
      });

      await axios.post(
        `${API}/appeal/complete`,
        { appeal_id },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setStage('done');
    } catch (err) {
      const detail =
        err.response?.data?.detail || err.message || 'Something went wrong. Please try again.';
      toast.error(detail);
      setStage('idle');
    }
  };

  if (stage === 'done') {
    return (
      <div className="min-h-screen bg-ink flex items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.21, 0.47, 0.32, 0.98] }}
          className="max-w-md w-full rounded-2xl border border-electric/30 bg-white/[0.02] p-12 text-center"
        >
          <CheckCircle2 size={48} className="text-cyan mx-auto" />
          <h2 className="mt-6 font-heading text-2xl font-semibold text-white">Appeal received.</h2>
          <p className="mt-4 text-base leading-relaxed text-slate-400">
            Our team will review your documentation for{' '}
            <span className="text-white font-medium">{track.track_name}</span> and follow up at{' '}
            <a href={`mailto:${BRAND.email}`} className="text-electric hover:underline">
              {BRAND.email}
            </a>.
          </p>
          <Link
            to="/vault"
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-gradient-brand px-7 py-3 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)]"
          >
            Back to My Vault
          </Link>
        </motion.div>
      </div>
    );
  }

  const isUploading = stage === 'uploading';

  return (
    <div className="min-h-screen bg-ink pt-28 pb-20 px-6">
      <div className="mx-auto max-w-xl">
        <div className="mb-8">
          <span className="text-xs font-bold uppercase tracking-[0.25em] text-electric">Appeal</span>
          <h1 className="mt-3 font-heading text-3xl font-semibold text-white">
            File a Copyright Appeal
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">
            Upload proof of ownership — a signed license, publishing agreement, or original session
            files — for our team to review.
          </p>
        </div>

        <div className="mb-6 rounded-xl border border-white/10 bg-white/[0.02] px-5 py-4">
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-500 mb-1">Track</p>
          <p className="text-white font-medium">{track.track_name}</p>
          <p className="text-slate-400 text-sm mt-0.5">
            {track.artist_name} · {track.genre}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 space-y-6"
        >
          <div className="space-y-2">
            <Label className="text-slate-300">
              Proof Document *{' '}
              <span className="text-slate-500">(PDF, JPG, PNG, DOC, DOCX — max 20 MB)</span>
            </Label>
            <div
              onClick={() => !isUploading && fileRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-8 text-center transition-colors ${
                file
                  ? 'border-electric/50 bg-electric/[0.05]'
                  : 'border-white/20 bg-ink/60 hover:border-electric/40 hover:bg-electric/[0.04]'
              } ${isUploading ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              {file ? (
                <>
                  <FileText size={24} className="text-electric" />
                  <div>
                    <p className="text-sm font-medium text-white">{file.name}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {(file.size / (1024 * 1024)).toFixed(1)} MB
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <Upload size={24} className="text-slate-500" />
                  <div>
                    <p className="text-sm text-slate-300">
                      Drop your file or <span className="text-electric">browse</span>
                    </p>
                    <p className="text-xs text-slate-600 mt-1">PDF, JPG, PNG, DOC, DOCX up to 20 MB</p>
                  </div>
                </>
              )}
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                className="hidden"
                onChange={(e) => handleFile(e.target.files?.[0])}
                disabled={isUploading}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="appeal-message" className="text-slate-300">
              Additional Notes <span className="text-slate-500">(optional)</span>
            </Label>
            <Textarea
              id="appeal-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              placeholder="Describe your ownership of this recording, relevant context, or where to find additional documentation."
              disabled={isUploading}
              className="border-white/10 bg-ink text-white placeholder:text-slate-600 focus-visible:ring-electric"
            />
          </div>

          {isUploading && (
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-slate-400">
                <span>
                  {uploadProgress < 100 ? `Uploading… ${uploadProgress}%` : 'Submitting appeal…'}
                </span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-white/10 overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-electric"
                  initial={{ width: 0 }}
                  animate={{ width: `${uploadProgress}%` }}
                  transition={{ ease: 'linear' }}
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={isUploading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-gradient-brand px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] disabled:opacity-60"
          >
            {isUploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {isUploading ? 'Uploading…' : 'Submit Appeal'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-600">
          Questions? Email us at{' '}
          <a
            href={`mailto:${BRAND.email}`}
            className="text-slate-400 hover:text-white transition-colors"
          >
            {BRAND.email}
          </a>
        </p>
      </div>
    </div>
  );
};

export default AppealPage;
