import React, { useState } from 'react';
import { useAuth, useUser } from '@clerk/clerk-react';
import { toast } from 'sonner';
import Modal from '../sync/Modal';
import { accountApi, errorMessage } from '../sync/api';

// "Set up buyer access" prompt (Brief 23 C2). On Continue it grants buyer access, reloads the
// Clerk user so the new metadata is live, then calls onGranted. Only artists without buyer
// access ever see it.
const BuyerAccessModal = ({ onClose, onGranted }) => {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [busy, setBusy] = useState(false);

  const go = async () => {
    setBusy(true);
    try {
      await accountApi.buyerAccess(getToken);
      await user?.reload();
      onGranted();
    } catch (err) {
      toast.error(errorMessage(err, 'Could not set up buyer access. Please try again.'));
      setBusy(false);
    }
  };

  return (
    <Modal open title="Set up buyer access" onClose={busy ? () => {} : onClose}>
      <p className="text-sm text-slate-300">
        Browse and license songs with the login you already have. Your artist Vault stays the same.
      </p>
      <div className="mt-5 flex justify-end gap-2.5">
        <button type="button" onClick={onClose} disabled={busy}
          className="rounded-full border border-white/10 px-5 py-2 text-sm text-slate-200 disabled:opacity-50">
          Not now
        </button>
        <button type="button" onClick={go} disabled={busy}
          className="rounded-full bg-gradient-brand px-6 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? 'Setting up…' : 'Continue'}
        </button>
      </div>
    </Modal>
  );
};

export default BuyerAccessModal;
