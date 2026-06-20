import React, { useState, useEffect } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { NAV_LINKS, BRAND } from '../content';

const Logo = () => (
  <Link to="/" data-testid="logo-link" className="flex items-center group">
    <img
      src={BRAND.logo}
      alt="oVoxi"
      className="h-10 w-auto transition-transform group-hover:scale-105"
    />
  </Link>
);

export const Header = () => {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
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
          <Logo />

          <nav className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                data-testid={`nav-${l.label.toLowerCase()}`}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive ? 'text-gradient-brand' : 'text-slate-400 hover-text-gradient'
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>

          <div className="hidden md:flex items-center gap-3">
            <a
              href="https://airtable.com/appmcBnXvP82ydQCz/pag6udQiv3QTWYG3m/form"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="header-artist-cta"
              className="text-sm font-medium text-slate-300 hover-text-gradient transition-colors"
            >
              Join as Artist
            </a>
            <Link
              to="/contact?interest=ai_company"
              data-testid="header-partnership-cta"
              className="rounded-full bg-gradient-brand px-5 py-2 text-sm font-semibold text-white transition-all hover:shadow-[0_0_24px_rgba(194,24,91,0.6)]"
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
