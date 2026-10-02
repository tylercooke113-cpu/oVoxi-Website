import { useState, useEffect, useCallback } from 'react';
import { agreementApi } from './agreementApi';

// Loads the agreement status once when signed in. On failure, status stays null
// (unknown) and callers fail open, per decision 7; the server is the real gate.
export function useAgreementStatus(getToken, enabled) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const data = await agreementApi.status(getToken);
      setStatus(data);
      setError(null);
    } catch (err) {
      setStatus(null);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [enabled, getToken]);

  useEffect(() => { refresh(); }, [refresh]);

  const needsSignature = !!(status && status.required && !status.signed);
  return { status, loading, error, refresh, needsSignature };
}
