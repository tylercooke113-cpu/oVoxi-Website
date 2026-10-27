import axios from 'axios';
import { API, authed } from '../sync/api';

// OVOXI Wallet (Brief 27). Money is integer cents from the server.
export const money = (cents) => {
  const n = Number(cents || 0);
  return `${n < 0 ? '-' : ''}$${(Math.abs(n) / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const walletApi = {
  me: async (getToken) => (await axios.get(`${API}/wallet/me`, await authed(getToken))).data,
  connect: async (getToken, country) =>
    (await axios.post(`${API}/wallet/connect`, { country }, await authed(getToken))).data,
  status: async (getToken) => (await axios.get(`${API}/wallet/connect/status`, await authed(getToken))).data,
  dashboard: async (getToken) => (await axios.post(`${API}/wallet/dashboard-link`, null, await authed(getToken))).data.url,
  statement: async (getToken, period) =>
    (await axios.get(`${API}/wallet/statements/${period}`, await authed(getToken))).data.url,
};

export const adminWalletApi = {
  overview: async (getToken, period) =>
    (await axios.get(`${API}/admin/wallet/overview`, { params: period ? { period } : {}, ...(await authed(getToken)) })).data,
  close: async (getToken, period) => (await axios.post(`${API}/admin/wallet/close`, { period }, await authed(getToken))).data,
  pay: async (getToken, period) => (await axios.post(`${API}/admin/wallet/payouts`, { period }, await authed(getToken))).data,
  hold: async (getToken, body) => (await axios.post(`${API}/admin/wallet/holds`, body, await authed(getToken))).data,
  release: async (getToken, trackId) =>
    (await axios.delete(`${API}/admin/wallet/holds/${encodeURIComponent(trackId)}`, await authed(getToken))).data,
  exclusives: async (getToken) => (await axios.get(`${API}/admin/sync/exclusive-licenses`, await authed(getToken))).data,
  recordPayment: async (getToken, licenseId, body) =>
    (await axios.post(`${API}/admin/sync/exclusive-licenses/${encodeURIComponent(licenseId)}/payments`, body,
      await authed(getToken))).data,
};
