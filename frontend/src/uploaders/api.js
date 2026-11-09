import axios from 'axios';
import { API, authed } from '../sync/api';

// Brief 28 Part D1: the artist's Authorized Uploaders (Upload Authorization v1).
export const uploadersApi = {
  list: async (getToken) =>
    (await axios.get(`${API}/vault/uploaders`, await authed(getToken))).data.uploaders || [],
  preview: async (getToken, body) =>
    (await axios.post(`${API}/vault/uploaders/preview`, body, await authed(getToken))).data,
  create: async (getToken, body) =>
    (await axios.post(`${API}/vault/uploaders`, body, await authed(getToken))).data.uploader,
  revoke: async (getToken, id) =>
    (await axios.delete(`${API}/vault/uploaders/${encodeURIComponent(id)}`, await authed(getToken))).data,
  // Brief 28 D6: admin list of every authorization (filters: status, artist, uploader).
  adminList: async (getToken, params = {}) =>
    (await axios.get(`${API}/admin/uploaders`, { params, ...(await authed(getToken)) })).data.uploaders || [],
};

// Same order and values as the backend (_clean_uploader_uses, PERSON_ROLES).
export const USES = [['sync', 'Sync placements'], ['ai_training', 'AI training']];
export const USE_SHORT = { sync: 'Sync', ai_training: 'AI training' };
export const PERSON_ROLES = ['Engineer', 'Studio owner', 'Producer', 'Manager'];

export const STATUS = {
  active: ['Active', 'ok'],
  awaiting_uploader: ['Waiting for uploader to sign', 'warn'],
  revoked: ['Revoked', 'off'],
  declined: ['Declined', 'off'],
  expired: ['Link expired', 'off'],
  ended_by_uploader: ['Ended by uploader', 'off'],
  ended_agreement: ['Ended', 'off'],
};

export const shortDate = (iso) =>
  (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '');

// Brief 28 Part D2: the invited uploader's side (/authorize/:token). Signed in with the invited email.
export const authorizeApi = {
  get: async (getToken, token) =>
    (await axios.get(`${API}/authorize/${encodeURIComponent(token)}`, await authed(getToken))).data,
  sign: async (getToken, token, body) =>
    (await axios.post(`${API}/authorize/${encodeURIComponent(token)}/sign`, body, await authed(getToken))).data,
  decline: async (getToken, token, reason) =>
    (await axios.post(`${API}/authorize/${encodeURIComponent(token)}/decline`,
      { reason: reason || null }, await authed(getToken))).data,
};

// Brief 28 D3: the artists the signed-in user can upload for (person authorizations, plus
// every OVOXI authorization for admins). Each has licensor_name, the locked legal name.
export const uploaderApi = {
  artists: async (getToken) =>
    (await axios.get(`${API}/uploader/artists`, await authed(getToken))).data.artists || [],
};
