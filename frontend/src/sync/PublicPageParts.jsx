import React from 'react';
import { Link } from 'react-router-dom';

export const NotFound = () => (
  <div className="flex min-h-[60vh] flex-col items-center justify-center px-6 text-center" data-testid="public-not-found">
    <h1 className="font-heading text-3xl font-semibold text-white">Page not found</h1>
    <p className="mt-2 text-slate-400">This page doesn't exist or isn't available.</p>
    <Link to="/" className="mt-6 rounded-full border border-white/10 px-5 py-2 text-sm text-slate-300 hover:text-white">Go home</Link>
  </div>
);

// Shown to the owner and admins while the page is not public (PRD-03 6.2).
export const VisibilityBanner = ({ viewer }) => {
  if (!viewer || viewer.public) return null;
  const text = viewer.is_admin && !viewer.is_owner
    ? 'Admin preview. This page is only visible to admins and the artist until it is public.'
    : 'Only you and oVoxi can see this page right now.';
  return (
    <div className="mx-auto mt-6 max-w-5xl px-4" data-testid="visibility-banner">
      <div className="rounded-xl border border-cyan/30 bg-cyan/[0.06] px-4 py-2.5 text-[13px] text-sky-200">{text}</div>
    </div>
  );
};

export const Initials = ({ name, size = 132, className = '' }) => (
  <div className={`flex flex-none items-center justify-center rounded-full bg-gradient-brand font-heading font-extrabold text-white ${className}`}
    style={{ width: size, height: size, fontSize: size / 3 }} aria-hidden="true">
    {(name || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()}
  </div>
);

export const Avatar = ({ profile, size = 132 }) => (
  profile?.photo_url
    ? <img src={profile.photo_url} alt={profile.display_name} width={size} height={size}
        className="flex-none rounded-full object-cover" style={{ width: size, height: size }} />
    : <Initials name={profile?.display_name} size={size} />
);
