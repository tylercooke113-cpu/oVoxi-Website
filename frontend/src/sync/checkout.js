import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '@clerk/clerk-react';
import { API, maybeAuthed } from './api';

// PRD-03 phase 6b: checkout, success-page and download-page calls. Prices always come
// from the server (decision 27); the client only ever sends the tier and add-on choice.

export const fmtMoney = (cents) => {
  if (cents == null) return '';
  const dollars = cents / 100;
  return `$${Number.isInteger(dollars) ? dollars : dollars.toFixed(2)}`;
};

export const checkoutApi = {
  config: async (getToken, isSignedIn) =>
    (await axios.get(`${API}/sync/checkout/config`, await maybeAuthed(getToken, isSignedIn))).data,
  start: async (body, getToken, isSignedIn) =>
    (await axios.post(`${API}/sync/checkout`, body, await maybeAuthed(getToken, isSignedIn))).data,
  bySession: async (sessionId) =>
    (await axios.get(`${API}/sync/orders/by-session/${encodeURIComponent(sessionId)}`)).data,
  downloads: async (token) =>
    (await axios.get(`${API}/sync/downloads/${encodeURIComponent(token)}`)).data,
  downloadFile: async (token, name) =>
    (await axios.post(`${API}/sync/downloads/${encodeURIComponent(token)}/${encodeURIComponent(name)}`)).data,
};

// One config request per page and sign-in state, shared by every License button on it.
const cache = new Map();
export const loadCheckoutConfig = (getToken, isSignedIn, userId, fresh = false) => {
  const key = isSignedIn ? `u:${userId}` : 'anon';
  if (fresh || !cache.has(key)) {
    cache.set(key, checkoutApi.config(getToken, isSignedIn).catch(() => {
      cache.delete(key);
      return { can_checkout: false };
    }));
  }
  return cache.get(key);
};

export const useCheckoutConfig = () => {
  const { getToken, isSignedIn, isLoaded, userId } = useAuth();
  const [config, setConfig] = useState(null);
  useEffect(() => {
    if (!isLoaded) return undefined;
    let alive = true;
    loadCheckoutConfig(getToken, isSignedIn, userId).then((c) => alive && setConfig(c));
    return () => { alive = false; };
  }, [getToken, isSignedIn, isLoaded, userId]);
  const refresh = async () => {
    const c = await loadCheckoutConfig(getToken, isSignedIn, userId, true);
    setConfig(c);
    return c;
  };
  return { config, refresh, getToken, isSignedIn };
};
