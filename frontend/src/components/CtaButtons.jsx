import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export const PrimaryCTA = ({ to, children, testid, className = '' }) => (
  <Link
    to={to}
    data-testid={testid}
    className={`group inline-flex items-center justify-center gap-2 rounded-full bg-electric px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(0,102,255,0.55)] ${className}`}
  >
    {children}
    <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
  </Link>
);

export const GhostCTA = ({ to, children, testid, className = '' }) => (
  <Link
    to={to}
    data-testid={testid}
    className={`inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/[0.03] px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:border-electric/50 hover:bg-white/[0.06] ${className}`}
  >
    {children}
  </Link>
);
