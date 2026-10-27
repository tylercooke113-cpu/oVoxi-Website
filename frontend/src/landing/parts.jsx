import React from 'react';
import { Link } from 'react-router-dom';

export const Arrow = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Check = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" className="shrink-0">
    <path d="M4 10.5l4 4 8-9" fill="none" stroke="#4FC3F7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const BTN = 'inline-flex items-center gap-2 rounded-full font-bold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan';
const KIND = {
  artist: 'bg-[#8E44CC] text-white hover:bg-[#7D3AB6]',
  buyer: 'bg-[#F4F4F6] text-black hover:bg-white',
  ghost: 'border border-[#3F3F46] text-[#F4F4F6] hover:bg-white/10',
};
const SIZE = { md: 'px-6 py-3.5 text-[15px]', lg: 'px-7 py-4 text-base' };

export const ButtonLink = ({ to, kind = 'artist', size = 'md', arrow, children, testid, className = '' }) => (
  <Link to={to} data-testid={testid} className={`${BTN} ${KIND[kind]} ${SIZE[size]} ${className}`}>
    {children}{arrow && <Arrow />}
  </Link>
);

export const Eyebrow = ({ color = 'text-[#A1A1AA]', children }) => (
  <p className={`m-0 text-[13px] uppercase tracking-[0.12em] ${color}`}>{children}</p>
);
