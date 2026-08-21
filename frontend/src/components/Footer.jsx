import React from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { BRAND } from '../content';

const COLUMNS = [
  {
    heading: 'Company',
    links: [
      { label: 'Contact', to: '/contact' },
    ],
  },
  {
    heading: 'Catalog',
    links: [
      { label: 'For AI & Enterprise', to: '/contact?interest=ai_company' },
    ],
  },
];

export const Footer = () => (
  <footer data-testid="site-footer" className="border-t border-white/10 bg-black">
    <div className="mx-auto max-w-7xl px-6 lg:px-8 py-16">
      <div className="grid grid-cols-1 gap-12 md:grid-cols-3">
        <div>
          <div className="flex items-center">
            <img src={BRAND.logo} alt="oVoxi" className="h-10 w-auto" />
          </div>
          <a
            href={`mailto:${BRAND.email}`}
            data-testid="footer-email"
            className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-slate-300 hover-text-gradient transition-colors"
          >
            <Mail size={16} /> {BRAND.email}
          </a>
        </div>

        {COLUMNS.map((col) => (
          <div key={col.heading}>
            <h4 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">{col.heading}</h4>
            <ul className="mt-4 space-y-3">
              {col.links.map((l) => (
                <li key={l.label}>
                  <Link
                    to={l.to}
                    data-testid={`footer-link-${l.label.toLowerCase().replace(/[^a-z]+/g, '-')}`}
                    className="text-sm text-slate-400 hover-text-gradient transition-colors"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mt-14 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-8 sm:flex-row">
        <p className="text-xs text-slate-500">
          © {new Date().getFullYear()} oVoxi · {BRAND.domain}
        </p>
        <div className="flex items-center gap-6 text-xs text-slate-500">
          <Link to="/privacy" data-testid="footer-link-privacy" className="hover:text-slate-300 transition-colors">
            Privacy
          </Link>
          <Link to="/terms" data-testid="footer-link-terms" className="hover:text-slate-300 transition-colors">
            Terms
          </Link>
        </div>
      </div>
    </div>
  </footer>
);
