import React, { useEffect } from 'react';

// Minimal accessible modal for the Vault (no new packages).
const Modal = ({ open, title, children, onClose }) => {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-white/10 bg-[#0A0A0C] p-6"
      >
        <h4 className="font-heading text-lg font-semibold text-white">{title}</h4>
        <div className="mt-3">{children}</div>
      </div>
    </div>
  );
};

export default Modal;
