import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useUser } from '@clerk/clerk-react';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { checkoutApi } from './checkout';
import { TIER_LABELS } from './DownloadPage';

// /sync/success?session_id=... (PRD-03 7.2 step 6). Polls until the order is delivered:
// every 2 s for the first minute, then every 5 s up to 3 minutes.

const FAST_MS = 2000;
const SLOW_MS = 5000;
const FAST_FOR_MS = 60000;
const GIVE_UP_MS = 180000;

const Shell = ({ children }) => (
  <div className="flex min-h-screen items-start justify-center bg-ink px-4 pb-20 pt-32" data-testid="success-page">
    <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.015] p-7 text-center">{children}</div>
  </div>
);

const SuccessPage = () => {
  const [params] = useSearchParams();
  const { isSignedIn } = useUser();
  const sessionId = params.get('session_id') || '';
  const [state, setState] = useState({ phase: 'processing', order: null });

  useEffect(() => {
    if (!sessionId) { setState({ phase: 'missing', order: null }); return undefined; }
    let alive = true;
    let timer;
    const started = Date.now();
    const tick = async () => {
      try {
        const order = await checkoutApi.bySession(sessionId);
        if (!alive) return;
        if (order.status !== 'processing') { setState({ phase: order.status, order }); return; }
        setState({ phase: 'processing', order });
      } catch (err) {
        if (!alive) return;
        if (err?.response?.status === 404) { setState({ phase: 'missing', order: null }); return; }
      }
      const elapsed = Date.now() - started;
      if (elapsed >= GIVE_UP_MS) { setState((s) => ({ ...s, phase: 'slow' })); return; }
      timer = setTimeout(tick, elapsed < FAST_FOR_MS ? FAST_MS : SLOW_MS);
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [sessionId]);

  const { phase, order } = state;
  if (phase === 'ready') {
    return (
      <Shell>
        <CheckCircle2 size={36} className="mx-auto text-cyan" />
        <h1 className="mt-3 font-heading text-2xl font-extrabold text-white">Your license is ready</h1>
        <p className="mt-1 text-sm text-slate-400">
          {order.track_title} by {order.artist_display_name} · {TIER_LABELS[order.tier] || order.tier}{order.include_stems ? ' + stems' : ''}
        </p>
        <p className="mt-1 text-xs text-slate-500">License ID {order.license_id}</p>
        <Link to={`/license/${order.download_token}`} data-testid="download-link"
          className="mt-6 flex h-11 items-center justify-center rounded-full bg-gradient-brand text-sm font-medium text-white">
          Download your files
        </Link>
        <p className="mt-3 text-xs text-slate-500">Bookmark the download page. The link works for 30 days, with 10 downloads per file.</p>
        {!isSignedIn && order.buyer_email_masked && (
          <p className="mt-4 border-t border-white/10 pt-4 text-xs text-slate-400">
            Keep all your licenses in one place.{' '}
            <Link to="/signup?next=/account" className="text-cyan hover:underline">
              Create an account with {order.buyer_email_masked}
            </Link>{' '}
            to see this license, its certificate and downloads any time.
          </p>
        )}
      </Shell>
    );
  }
  if (phase === 'processing') {
    return (
      <Shell>
        <Loader2 size={32} className="mx-auto animate-spin text-electric" />
        <h1 className="mt-3 font-heading text-2xl font-extrabold text-white">Confirming your payment</h1>
        <p className="mt-1 text-sm text-slate-400">This usually takes a few seconds. Keep this page open.</p>
      </Shell>
    );
  }
  const messages = {
    slow: ['Taking longer than usual', 'Your payment may still be processing. Refresh this page in a minute, or email tyler@ovoxi.net and include this page\'s link.'],
    failed: ['Checkout didn\'t complete', 'Your payment wasn\'t taken. You can start again from the track page.'],
    refunded: ['This order was refunded', 'The license is no longer valid. Email tyler@ovoxi.net with any questions.'],
    missing: ['Order not found', 'This link doesn\'t match an order. If you paid, email tyler@ovoxi.net with your receipt.'],
  };
  const [title, body] = messages[phase] || messages.missing;
  return (
    <Shell>
      <h1 className="font-heading text-2xl font-extrabold text-white">{title}</h1>
      <p className="mt-2 text-sm text-slate-400">{body}</p>
      <Link to="/sync" className="mt-6 inline-block rounded-full border border-white/10 px-5 py-2 text-sm text-slate-300 hover:text-white">Back to the library</Link>
    </Shell>
  );
};

export default SuccessPage;
