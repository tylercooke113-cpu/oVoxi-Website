import React, { useState } from 'react';
import LicenseModal from './LicenseModal';
import { useCheckoutConfig } from './checkout';

// Live for anyone the server says can check out (admins with a test key until launch,
// decision 25); "coming soon" for everyone else.

const LicenseButton = ({ track }) => {
  const { config, refresh, getToken, isSignedIn } = useCheckoutConfig();
  const [open, setOpen] = useState(false);

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
      <button type="button" onClick={() => setOpen(true)} data-testid={`license-${track.id}`}
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
