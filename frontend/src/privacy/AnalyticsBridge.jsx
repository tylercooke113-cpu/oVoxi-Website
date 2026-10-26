import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { isPrerender } from '../lib/consent';
import { setPath, start, stop } from '../lib/analytics';
import useConsent from './useConsent';

// Starts PostHog only when the choice in force allows analytics, stops it when it does
// not, and tells it about route changes so replay pauses on private pages.
export default function AnalyticsBridge() {
  const choice = useConsent();
  const { pathname } = useLocation();

  useEffect(() => { setPath(pathname); }, [pathname]);

  useEffect(() => {
    if (choice === undefined || isPrerender()) return;   // not known yet
    if (choice && choice.analytics) start();
    else stop();
  }, [choice]);

  return null;
}
