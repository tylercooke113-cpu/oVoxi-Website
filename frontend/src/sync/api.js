import axios from 'axios';

// Shared by the Vault sync components. Same backend as the rest of the app.
export const API = 'https://ovoxi-website-production.up.railway.app/api';

export const authed = async (getToken) => ({
  headers: { Authorization: `Bearer ${await getToken()}` },
});

// FastAPI validation errors arrive as an array; pydantic prefixes validator
// messages with "Value error, ".
export const errorMessage = (err, fallback = 'Something went wrong. Please try again.') => {
  const detail = err?.response?.data?.detail;
  const raw = Array.isArray(detail) ? detail[0]?.msg : detail;
  if (typeof raw === 'string' && raw) return raw.replace(/^Value error, /, '');
  if (err?.code === 'ERR_NETWORK') return 'Could not reach the server. Check your connection.';
  return fallback;
};

// Public pages send a token only when someone is signed in (owner / admin preview).
export const maybeAuthed = async (getToken, isSignedIn) => {
  if (!isSignedIn) return {};
  try { return await authed(getToken); } catch { return {}; }
};

export const publicApi = {
  library: async (params, getToken, isSignedIn) =>
    (await axios.get(`${API}/sync/tracks`, { params, ...(await maybeAuthed(getToken, isSignedIn)) })).data,
  artist: async (slug, getToken, isSignedIn) =>
    (await axios.get(`${API}/sync/artists/${encodeURIComponent(slug)}`, await maybeAuthed(getToken, isSignedIn))).data,
  track: async (id, getToken, isSignedIn) =>
    (await axios.get(`${API}/sync/tracks/${encodeURIComponent(id)}`, await maybeAuthed(getToken, isSignedIn))).data,
  waveform: async (id, getToken, isSignedIn) =>
    (await axios.get(`${API}/sync/tracks/${encodeURIComponent(id)}/waveform`, await maybeAuthed(getToken, isSignedIn))).data,
  preview: async (id, getToken, isSignedIn) =>
    (await axios.post(`${API}/sync/tracks/${encodeURIComponent(id)}/preview`, null, await maybeAuthed(getToken, isSignedIn))).data,
};

export const api = {
  patchMetadata: async (getToken, id, body) =>
    (await axios.patch(`${API}/vault/tracks/${id}/metadata`, body, await authed(getToken))).data,
  changeConsent: async (getToken, id, body) =>
    (await axios.post(`${API}/vault/tracks/${id}/consent`, body, await authed(getToken))).data,
  getProfile: async (getToken) =>
    (await axios.get(`${API}/sync/profile`, await authed(getToken))).data,
  putProfile: async (getToken, body) =>
    (await axios.put(`${API}/sync/profile`, body, await authed(getToken))).data,
  presignPhoto: async (getToken, body) =>
    (await axios.post(`${API}/sync/profile/photo/presign`, body, await authed(getToken))).data,
  // Processing is normally about a second; 60 s means something went wrong.
  completePhoto: async (getToken, uploadId) =>
    (await axios.post(`${API}/sync/profile/photo/complete`, { upload_id: uploadId },
      { ...(await authed(getToken)), timeout: 60000 })).data,
  deletePhoto: async (getToken) =>
    (await axios.delete(`${API}/sync/profile/photo`, await authed(getToken))).data,
  adminProfiles: async (getToken) =>
    (await axios.get(`${API}/admin/sync/profiles`, await authed(getToken))).data,
  adminDelist: async (getToken, id, delisted) =>
    (await axios.post(`${API}/admin/sync/tracks/${id}/delist`, { delisted }, await authed(getToken))).data,
  adminHide: async (getToken, slug, hidden) =>
    (await axios.post(`${API}/admin/sync/profiles/${slug}/hide`, { hidden }, await authed(getToken))).data,
};
