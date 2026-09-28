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

export const api = {
  patchMetadata: async (getToken, id, body) =>
    (await axios.patch(`${API}/vault/tracks/${id}/metadata`, body, await authed(getToken))).data,
  changeConsent: async (getToken, id, body) =>
    (await axios.post(`${API}/vault/tracks/${id}/consent`, body, await authed(getToken))).data,
  getProfile: async (getToken) =>
    (await axios.get(`${API}/sync/profile`, await authed(getToken))).data,
  putProfile: async (getToken, body) =>
    (await axios.put(`${API}/sync/profile`, body, await authed(getToken))).data,
};
