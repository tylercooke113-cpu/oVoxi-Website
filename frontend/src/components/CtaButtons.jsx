import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

const primaryClass = (className) =>
  `group inline-flex items-center justify-center gap-2 rounded-full bg-gradient-brand px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:shadow-[0_0_28px_rgba(194,24,91,0.55)] ${className}`;

export const PrimaryCTA = ({ to, children, testid, className = '' }) => {
  const inner = (
    <>
      {children}
      <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
    </>
  );
  return to?.startsWith('http') ? (
    <a href={to} target="_blank" rel="noopener noreferrer" data-testid={testid} className={primaryClass(className)}>
      {inner}
    </a>
  ) : (
    <Link to={to} data-testid={testid} className={primaryClass(className)}>
      {inner}
    </Link>
  );
};

const ghostClass = (className) =>
  `inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/[0.03] px-7 py-3.5 text-sm font-semibold text-white transition-all duration-300 hover:border-electric/50 hover:bg-white/[0.06] ${className}`;

export const GhostCTA = ({ to, children, testid, className = '' }) =>
  to?.startsWith('http') ? (
    <a href={to} target="_blank" rel="noopener noreferrer" data-testid={testid} className={ghostClass(className)}>
      {children}
    </a>
  ) : (
    <Link to={to} data-testid={testid} className={ghostClass(className)}>
      {children}
    </Link>
  );
