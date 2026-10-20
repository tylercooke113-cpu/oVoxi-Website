import React from 'react';
import { CheckCircle2, AlertCircle, Loader2, Music2 } from 'lucide-react';
import { songMissing } from './SongForm';

const fileSummary = (file) =>
  file ? `${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)` : 'No file yet';

// Status chip for a song that is queued / uploading / received / failed.
const StatusChip = ({ song }) => {
  if (song.status === 'uploading') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-slate-300">
        <Loader2 size={14} className="animate-spin text-electric" />
        Uploading… {song.progress}%
      </span>
    );
  }
  if (song.status === 'queued') {
    return <span className="text-xs text-slate-500">Queued</span>;
  }
  if (song.status === 'received') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-cyan">
        <CheckCircle2 size={14} /> Received
      </span>
    );
  }
  if (song.status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-red-400">
        <AlertCircle size={14} /> Failed
      </span>
    );
  }
  return null;
};

// A collapsed song. `locked` hides Edit/Remove while a batch is running.
const SongSummaryRow = ({ song, index, locked, onEdit, onRemove }) => {
  const missing = songMissing(song);
  const showStatus = song.status !== 'draft';

  return (
    <div
      data-testid={`upload-summary-${index}`}
      className="flex items-start justify-between gap-4 rounded-xl border border-white/10 bg-white/[0.02] px-5 py-4"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Music2 size={16} className="shrink-0 text-electric" />
          <p className="truncate text-sm font-medium text-white">
            Song {index + 1}: {song.form.track_name || 'Untitled'}
          </p>
        </div>
        <p className="mt-1 truncate text-xs text-slate-500">{fileSummary(song.file)}</p>

        {showStatus ? (
          <div className="mt-2">
            <StatusChip song={song} />
            {song.status === 'failed' && song.error && (
              <p className="mt-1 text-xs text-red-400/80">{song.error}</p>
            )}
          </div>
        ) : (
          <div className="mt-2">
            {missing.length === 0 ? (
              <span className="inline-flex items-center gap-1.5 text-xs text-cyan">
                <CheckCircle2 size={14} /> Ready
              </span>
            ) : (
              <span className="text-xs text-amber-400">Missing: {missing.join(', ')}</span>
            )}
          </div>
        )}
      </div>

      {!locked && (
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            data-testid={`upload-edit-${index}`}
            onClick={onEdit}
            className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 transition-colors hover:border-electric/40 hover:text-white"
          >
            Edit
          </button>
          <button
            type="button"
            data-testid={`upload-remove-${index}`}
            onClick={onRemove}
            className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400 transition-colors hover:border-red-400/40 hover:text-red-300"
          >
            Remove
          </button>
        </div>
      )}
    </div>
  );
};

export default SongSummaryRow;
