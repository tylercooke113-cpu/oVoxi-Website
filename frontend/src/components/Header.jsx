import React, { useState, useEffect } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Menu, X, ChevronDown } from 'lucide-react';
import { useUser } from '@clerk/clerk-react';
import { NAV_LINKS } from '../content';

const Logo = () => (
  <Link to="/" data-testid="logo-link" className="flex items-center group">
    <img
      src="/logo.png"
      alt="oVoxi"
      className="h-10 w-auto transition-opacity group-hover:opacity-80"
    />
  </Link>
);

export const Header = () => {
  const { isSignedIn } = useUser();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if (!e.target.closest('[data-dropdown]')) setDropdownOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const closeMenu = () => setOpen(false);

  return (
    <header
      data-testid="site-header"
      className={`fixed top-0 inset-x-0 z-50 transition-colors duration-300 ${
        scrolled ? 'bg-black/80 backdrop-blur-xl border-b border-white/10' : 'bg-transparent'
      }`}
    >
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">

          <div className="flex items-center gap-3">
            <Logo />
            <div className="relative" data-dropdown>
              <button
                onClick={() => setDropdownOpen((v) => !v)}
                className="flex items-center gap-1.5 text-sm font-medium text-slate-400 hover:text-white transition-colors"
              >
                <ChevronDown
                  size={16}
                  className={`transition-transform duration-200 ${dropdownOpen ? 'rotate-180' : ''}`}
                />
              </button>
              {dropdownOpen && (
                <div className="absolute top-full left-0 mt-2 w-48 rounded-xl border border-white/10 bg-black/95 backdrop-blur-xl py-2 shadow-xl">
                  {isSignedIn && (
                    <NavLink
                      to='/vault'
                      onClick={() => setDropdownOpen(false)}
                      className='block px-4 py-2.5 text-sm text-slate-300 hover:text-white hover-text-gradient transition-colors'
                    >
                      My Vault
                    </NavLink>
                  )}
                  {NAV_LINKS.map((l) => (
                    <NavLink
                      key={l.to}
                      to={l.to}
                      data-testid={`nav-${l.label.toLowerCase()}`}
                      onClick={() => setDropdownOpen(false)}
                      className="block px-4 py-2.5 text-sm text-slate-300 hover:text-white hover-text-gradient transition-colors"
                    >
                      {l.label}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Link
              to="/signup"
              data-testid="header-artist-cta"
              className="text-sm font-medium text-slate-300 hover-text-gradient transition-colors"
            >
              Join as Artist
            </Link>
            <Link
              to="/contact?interest=ai_company"
              data-testid="header-partnership-cta"
              className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(180,79,212,0.6)]"
            >
              Request Partnership
            </Link>
          </div>

          <button
            data-testid="mobile-menu-toggle"
            className="md:hidden text-white"
            onClick={() => setOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            {open ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {open && (
        <div data-testid="mobile-menu" className="md:hidden bg-black/95 backdrop-blur-xl border-b border-white/10">
          <div className="px-6 py-4 flex flex-col gap-4">
            {NAV_LINKS.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                onClick={closeMenu}
                data-testid={`mobile-nav-${l.label.toLowerCase()}`}
                className="text-base font-medium text-slate-300 hover-text-gradient"
              >
                {l.label}
              </Link>
            ))}
            <Link
              to="/contact?interest=ai_company"
              onClick={closeMenu}
              data-testid="mobile-partnership-cta"
              className="mt-2 rounded-full bg-gradient-brand px-5 py-2.5 text-center text-sm font-semibold text-white"
            >
              Request Partnership
            </Link>
          </div>
        </div>
      )}
    </header>
  );
};
