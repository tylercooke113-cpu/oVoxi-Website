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
  // Brief 20 B1: public pricing. Token sent only when signed in, to compute `visible` for admins.
  pricing: async (getToken, isSignedIn) =>
    (await axios.get(`${API}/sync/pricing`, await maybeAuthed(getToken, isSignedIn))).data,
};

export const api = {
  patchMetadata: async (getToken, id, body) =>
    (await axios.patch(`${API}/vault/tracks/${id}/metadata`, body, await authed(getToken))).data,
  changeConsent: async (getToken, id, body) =>
    (await axios.post(`${API}/vault/tracks/${id}/consent`, body, await authed(getToken))).data,
  setDeclarations: async (getToken, id, body) =>
    (await axios.post(`${API}/vault/tracks/${id}/declarations`, body, await authed(getToken))).data,
  // Agreement 3.6(c): presign, PUT the file straight to storage, then complete.
  uploadLoopLicense: async (getToken, trackId, index, file) => {
    const { data } = await axios.post(`${API}/vault/tracks/${trackId}/loops/${index}/license/presign`,
      { filename: file.name, content_type: file.type, file_size: file.size }, await authed(getToken));
    await axios.put(data.presigned_url, file, { headers: { 'Content-Type': data.content_type } });
    return (await axios.post(`${API}/vault/tracks/${trackId}/loops/${index}/license/complete`, null,
      await authed(getToken))).data;
  },
  cosignResend: async (getToken, trackId, requestId) =>
    (await axios.post(`${API}/vault/tracks/${trackId}/cosign/${requestId}/resend`, null, await authed(getToken))).data,
  cosignEditEmail: async (getToken, trackId, requestId, email) =>
    (await axios.patch(`${API}/vault/tracks/${trackId}/cosign/${requestId}`, { email }, await authed(getToken))).data,
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
  // Brief 25b D5 / D1 / F: exclusive sales and the two reviews.
  adminRecordExclusive: async (getToken, id, body) =>
    (await axios.post(`${API}/admin/sync/tracks/${id}/exclusive-licenses`, body, await authed(getToken))).data,
  adminExclusiveLicenses: async (getToken) =>
    (await axios.get(`${API}/admin/sync/exclusive-licenses`, await authed(getToken))).data,
  adminAiToolsReview: async (getToken, id, result, reason = '') =>
    (await axios.post(`${API}/admin/sync/tracks/${id}/ai-tools-review`, { result, reason }, await authed(getToken))).data,
  adminLoopLicense: async (getToken, id, index) =>
    (await axios.get(`${API}/admin/sync/tracks/${id}/loops/${index}/license`, await authed(getToken))).data,
  adminLoopReview: async (getToken, id, result, reason = '') =>
    (await axios.post(`${API}/admin/sync/tracks/${id}/loop-licenses-review`, { result, reason }, await authed(getToken))).data,
  adminHide: async (getToken, slug, hidden) =>
    (await axios.post(`${API}/admin/sync/profiles/${slug}/hide`, { hidden }, await authed(getToken))).data,
  adminOrders: async (getToken, params) =>
    (await axios.get(`${API}/admin/sync/orders`, { params, ...(await authed(getToken)) })).data,
  adminOrdersCsv: async (getToken, params) =>
    (await axios.get(`${API}/admin/sync/orders.csv`, { params, responseType: 'blob', ...(await authed(getToken)) })).data,
  adminResendEmail: async (getToken, orderId) =>
    (await axios.post(`${API}/admin/sync/orders/${encodeURIComponent(orderId)}/resend-email`, null, await authed(getToken))).data,
  adminReissueLink: async (getToken, orderId, sendEmail) =>
    (await axios.post(`${API}/admin/sync/orders/${encodeURIComponent(orderId)}/reissue-link`, { send_email: sendEmail }, await authed(getToken))).data,
};

// Brief 17: buyer account (any signed-in user) and the public verification page.
export const accountApi = {
  licenses: async (getToken) =>
    (await axios.get(`${API}/account/licenses`, await authed(getToken))).data,
  certificate: async (getToken, id) =>
    (await axios.get(`${API}/account/licenses/${encodeURIComponent(id)}/certificate`, await authed(getToken))).data.url,
  file: async (getToken, id, name) =>
    (await axios.post(`${API}/account/licenses/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`, null, await authed(getToken))).data.url,
  buyerAccess: async (getToken) =>
    (await axios.post(`${API}/account/buyer-access`, null, await authed(getToken))).data,
};

export const verifyApi = {
  get: async (id) => (await axios.get(`${API}/verify/${encodeURIComponent(id)}`)).data,
};

// Brief 18: public License Terms blocks and quote requests.
export const syncApi = {
  terms: async (version) => (await axios.get(`${API}/sync/terms/${encodeURIComponent(version)}`)).data,
  quote: async (body) => (await axios.post(`${API}/sync/quotes`, body)).data,
};

// Brief 19 subscriptions: checkout, billing portal, resume, status, project registration.
export const subscriptionsApi = {
  me: async (getToken) =>
    (await axios.get(`${API}/subscriptions/me`, await authed(getToken))).data,
  checkout: async (getToken, body) =>
    (await axios.post(`${API}/subscriptions/checkout`, body, await authed(getToken))).data.checkout_url,
  portal: async (getToken) =>
    (await axios.post(`${API}/subscriptions/portal`, null, await authed(getToken))).data.portal_url,
  resume: async (getToken) =>
    (await axios.post(`${API}/subscriptions/resume`, null, await authed(getToken))).data,
  register: async (getToken, body) =>
    (await axios.post(`${API}/subscriptions/register`, body, await authed(getToken))).data,
};

// Helper for any parent component: start Checkout and redirect to Stripe on success.
// A 409 (customer already has a plan) is returned as a typed result so the caller can
// show it in place; this does NOT redirect. Any other error propagates to the caller.
// Keeps SubscribeModal props-only: it never imports axios.
export const startSubscriptionCheckout = async (getToken, body) => {
  try {
    const url = await subscriptionsApi.checkout(getToken, body);
    window.location.assign(url);
    return { status: 'redirecting' };
  } catch (err) {
    if (err?.response?.status === 409) {
      return { status: 'already_subscribed', message: errorMessage(err) };
    }
    throw err;
  }
};
