import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import LicenseModal from './LicenseModal';
import { useCheckoutConfig } from './checkout';

// Live for anyone the server says can check out (admins with a test key until launch,
// decision 25); "coming soon" for everyone else.

const LicenseButton = ({ track }) => {
  const { config, refresh, getToken, isSignedIn } = useCheckoutConfig();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const loc = useLocation();
  const [params, setParams] = useSearchParams();

  // Reopen this track's pop-up after returning from buyer sign-up (Brief 23 C4).
  useEffect(() => {
    if (isSignedIn && track && params.get('license') === String(track.id)) {
      setOpen(true);
      const p = new URLSearchParams(params);
      p.delete('license');
      setParams(p, { replace: true });
    }
  }, [isSignedIn, track, params, setParams]);

  // Signed in: open the pop-up. Signed out: send to buyer sign-up and come back here.
  const onLicense = () => {
    if (isSignedIn) { setOpen(true); return; }
    const sep = loc.search ? '&' : '?';
    const next = `${loc.pathname}${loc.search}${sep}license=${track.id}`;
    navigate(`/signup?as=buyer&next=${encodeURIComponent(next)}`);
  };

  if (!track || !config?.can_checkout) {
    return (
      <button type="button" disabled title="Licensing opens soon"
        className="cursor-not-allowed whitespace-nowrap rounded-full border border-white/10 px-3 py-2 text-xs text-slate-500 sm:px-4">
        <span className="sm:hidden">License</span>
        <span className="hidden sm:inline">License · coming soon</span>
      </button>
    );
  }
  const from = Math.min(...config.tiers.map((t) => t.price_cents));
  return (
    <>
      <button type="button" onClick={onLicense} data-testid={`license-${track.id}`}
        className="whitespace-nowrap rounded-full bg-gradient-brand px-3 py-2 text-xs font-medium text-white sm:px-4">
        <span className="sm:hidden">License</span>
        <span className="hidden sm:inline">License · from ${from / 100}</span>
      </button>
      {open && (
        <LicenseModal track={track} config={config} refreshConfig={refresh} onClose={() => setOpen(false)}
          getToken={getToken} isSignedIn={isSignedIn} />
      )}
    </>
  );
};

export default LicenseButton;
