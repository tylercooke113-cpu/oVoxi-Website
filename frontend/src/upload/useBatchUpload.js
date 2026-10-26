import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { buildRightsPayload } from '../sync/RightsSection';
import { buildIntakePayload } from '../sync/SyncIntakeFields';
import { buildDeclarationsPayload, usesLoops } from './declarations';

export const API = 'https://ovoxi-website-production.up.railway.app/api';

export const APPROVAL_PENDING_MESSAGE =
  'Your account is pending approval. We will email you once you are cleared to upload.';
export const UPLOADS_PAUSED_MESSAGE = 'Uploads are temporarily paused. Please try again later.';
export const TOO_MANY_MESSAGE =
  'Some songs are still processing. Wait a few minutes, then press Retry.';
export const AGREEMENT_DETAIL = 'Sign the Artist Agreement before uploading.';
export const LICENSE_RETRY_MESSAGE = 'A loop license did not upload. Add it from your Vault.';

// FastAPI returns validation errors as an array; pydantic prefixes
// messages raised in validators with "Value error, ".
export const validationMessage = (detail) => {
  const raw = Array.isArray(detail) ? detail[0]?.msg : detail;
  if (!raw || typeof raw !== 'string') return null;
  return raw.replace(/^Value error, /, '');
};

// The single-song error-to-message logic, reused per song (brief A4).
export const uploadErrorMessage = (err) => {
  const status = err.response?.status;
  if (status === 403) {
    const serverDetail = err.response?.data?.detail;
    return (!serverDetail || serverDetail === 'Forbidden')
      ? APPROVAL_PENDING_MESSAGE
      : serverDetail;
  }
  if (status === 422) {
    return validationMessage(err.response?.data?.detail)
      || 'Please refresh the page and try again.';
  }
  if (err.response?.data?.detail) return err.response.data.detail;
  if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
    return 'Could not reach the server. Check your connection or try again shortly.';
  }
  if (status >= 500) return `Server error (${status}). Please try again.`;
  return err.message || 'Something went wrong. Please try again.';
};

// Classify an upload error into a batch-control signal.
//   agreement  -> uploader has not signed; open the modal, resume later
//   approval   -> account pending / forbidden; stop the batch
//   paused     -> uploads globally paused (503); stop the batch
//   too_many   -> open-submissions cap (429); stop, mark remaining with a clean message
//   retry_429  -> any other 429; wait and retry this one song once
//   fail       -> ordinary per-song failure; mark failed and continue
export const classifyError = (err) => {
  const status = err.response?.status;
  const detail = err.response?.data?.detail;
  if (status === 403 && detail === AGREEMENT_DETAIL) return 'agreement';
  if (status === 403) return 'approval';
  if (status === 503) return 'paused';
  if (status === 429 && typeof detail === 'string'
      && /too many uploads in progress/i.test(detail)) return 'too_many';
  if (status === 429) return 'retry_429';
  return 'fail';
};

// The existing three-step upload for one song. Body unchanged from the single-song page.
export const uploadOne = async (song, { getToken, api, onProgress }) => {
  const token = await getToken();
  const bpmNumber = parseFloat(song.bpm);
  const { data: presignData } = await axios.post(`${api}/upload/presign`, {
    artist_name: song.form.artist_name,
    track_name: song.form.track_name,
    genre: song.form.genre,
    genre_other: song.form.genre === 'Other' ? (song.form.genre_other || '').trim() : null,
    filename: song.file.name,
    file_size: song.file.size,
    consent_ai_training: song.consentAi,
    consent_sync: song.consentSync,
    consent_exclusive: !!song.consentExclusive,
    declarations: buildDeclarationsPayload(song.declarations),
    moods: song.moods,
    vocals: song.vocals,
    ...(song.bpmUnsure ? { bpm_unsure: true } : { bpm: Math.round(bpmNumber * 10) / 10 }),
    ...(song.keyUnsure ? { key_unsure: true } : { key: song.musicalKey }),
    rights: buildRightsPayload(song.rights),
    ...(song.consentSync ? { sync_intake: buildIntakePayload(song.intake) } : {}),
  }, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const { presigned_url, submission_id, content_type } = presignData;

  await axios.put(presigned_url, song.file, {
    headers: { 'Content-Type': content_type },
    onUploadProgress: (ev) => {
      if (ev.total) onProgress(Math.round((ev.loaded / ev.total) * 100));
    },
  });

  onProgress(100, 'finishing');   // file sent; waiting for storage and /complete
  const completeToken = await getToken();
  await axios.post(`${api}/upload/complete`, { submission_id }, {
    headers: { Authorization: `Bearer ${completeToken}` },
  });

  // Agreement 3.6(c): one license per loop. The song is already received, so a failed
  // license upload becomes a warning; the artist can add it from the Vault.
  let warning = null;
  if (usesLoops(song.declarations)) {
    for (let i = 0; i < song.declarations.loops.length; i += 1) {
      const file = song.declarations.loops[i].file;
      if (!file) continue;
      try {
        const auth = { headers: { Authorization: `Bearer ${await getToken()}` } };
        const { data } = await axios.post(`${api}/vault/tracks/${submission_id}/loops/${i}/license/presign`,
          { filename: file.name, content_type: file.type, file_size: file.size }, auth);
        await axios.put(data.presigned_url, file, { headers: { 'Content-Type': data.content_type } });
        await axios.post(`${api}/vault/tracks/${submission_id}/loops/${i}/license/complete`, null,
          { headers: { Authorization: `Bearer ${await getToken()}` } });
      } catch (err) {
        warning = LICENSE_RETRY_MESSAGE;
      }
    }
  }
  return { submissionId: submission_id, warning };
};

// doUpload may return the submission id (older tests) or { submissionId, warning }.
const asResult = (r) => (r && typeof r === 'object' ? r : { submissionId: r, warning: null });

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run a list of songs strictly one at a time through the three-step pipeline.
 * Dependencies are injected so this is testable without a DOM or real network.
 *
 * @param list      song objects to process, in order
 * @param deps.getToken   Clerk token getter
 * @param deps.api        API base URL
 * @param deps.patchSong  (key, partial) => void, merges a partial into a song by key
 * @param deps.doUpload   defaults to uploadOne; override in tests
 * @param deps.sleep      defaults to a real 30s wait; override in tests
 * @returns {Promise<{stopReason: null|'agreement'|'approval'|'paused'|'too_many', failed: number}>}
 */
export const runBatch = async (list, {
  getToken,
  api = API,
  patchSong,
  doUpload = uploadOne,
  sleep = (ms) => wait(ms),
}) => {
  const attempt = async (song) => asResult(await doUpload(song, {
    getToken,
    api,
    onProgress: (p, phase) => patchSong(song.key, { progress: p, ...(phase ? { phase } : {}) }),
  }));

  let failed = 0;
  for (let i = 0; i < list.length; i += 1) {
    const song = list[i];
    patchSong(song.key, { status: 'uploading', progress: 0, phase: 'uploading', error: null, warning: null });

    try {
      const { submissionId, warning } = await attempt(song);
      patchSong(song.key, { status: 'received', submissionId, progress: 100, warning });
      continue;
    } catch (err) {
      const kind = classifyError(err);

      // Stop the whole batch. Songs not yet sent stay queued; nothing received is touched.
      if (kind === 'agreement' || kind === 'approval' || kind === 'paused') {
        patchSong(song.key, { status: 'queued', progress: 0 });
        return { stopReason: kind };
      }

      // Open-submissions cap. Mark this song and every remaining queued song with the
      // clean message so "Retry failed songs" reads cleanly rather than a raw 429.
      if (kind === 'too_many') {
        for (let j = i; j < list.length; j += 1) {
          patchSong(list[j].key, { status: 'failed', error: TOO_MANY_MESSAGE, progress: 0 });
        }
        return { stopReason: 'too_many' };
      }

      // Any other 429: wait and retry this one song once, then continue either way.
      if (kind === 'retry_429') {
        await sleep(30000);
        patchSong(song.key, { progress: 0, phase: 'uploading' });
        try {
          const { submissionId, warning } = await attempt(song);
          patchSong(song.key, { status: 'received', submissionId, progress: 100, warning });
        } catch (err2) {
          const kind2 = classifyError(err2);
          if (kind2 === 'too_many') {
            for (let j = i; j < list.length; j += 1) {
              patchSong(list[j].key, { status: 'failed', error: TOO_MANY_MESSAGE, progress: 0 });
            }
            return { stopReason: 'too_many' };
          }
          failed += 1;
          patchSong(song.key, { status: 'failed', error: uploadErrorMessage(err2), progress: 0 });
        }
        continue;
      }

      // Ordinary failure: record it and keep going.
      failed += 1;
      patchSong(song.key, { status: 'failed', error: uploadErrorMessage(err), progress: 0 });
    }
  }

  return { stopReason: null, failed };
};

// Thin React wrapper: tracks the running flag and warns on unload during a run.
export const useBatchUpload = ({ getToken, api = API }) => {
  const [running, setRunning] = useState(false);
  const runningRef = useRef(false);

  useEffect(() => {
    const onBeforeUnload = (e) => {
      if (!runningRef.current) return undefined;
      e.preventDefault();
      e.returnValue = '';
      return '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);

  const run = useCallback(async (list, patchSong) => {
    setRunning(true);
    runningRef.current = true;
    try {
      return await runBatch(list, { getToken, api, patchSong });
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  }, [getToken, api]);

  return { running, run };
};
