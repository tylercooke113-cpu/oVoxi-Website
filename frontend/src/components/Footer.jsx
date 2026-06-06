import React from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { BRAND } from '../content';

const COLUMNS = [
  {
    heading: 'Company',
    links: [
      { label: 'About', to: '/about' },
      { label: 'Investors', to: '/investors' },
      { label: 'Contact', to: '/contact' },
    ],
  },
  {
    heading: 'Catalog',
    links: [
      { label: 'For Artists', to: '/artists' },
      { label: 'For AI & Enterprise', to: '/licensing' },
    ],
  },
  {
    heading: 'Get Started',
    links: [
      { label: 'Request Partnership', to: '/contact?interest=ai_company' },
      { label: 'Join as Artist', to: '/contact?interest=artist' },
      { label: 'Investor Inquiries', to: '/contact?interest=investor' },
    ],
  },
];

export const Footer = () => (
  <footer data-testid="site-footer" className="border-t border-white/10 bg-ink">
    <div className="mx-auto max-w-7xl px-6 lg:px-8 py-16">
      <div className="grid grid-cols-1 gap-12 md:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2">
            <span className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-electric/15 ring-1 ring-electric/40">
              <span className="h-3 w-3 rounded-full bg-cyan shadow-[0_0_12px_#00E5FF]" />
            </span>
            <span className="font-heading text-lg font-semibold text-white">
              oVoxi<span className="text-electric">.ai</span>
            </span>
          </div>
          <p className="mt-5 max-w-sm text-sm leading-relaxed text-slate-400">
            A licensed music infrastructure company for the AI era. Emerging-first, fully licensed,
            AI-ready catalogs built for the next wave of generative sound.
          </p>
          <a
            href={`mailto:${BRAND.email}`}
            data-testid="footer-email"
            className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-electric transition-colors"
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
                    className="text-sm text-slate-400 hover:text-white transition-colors"
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
          © {new Date().getFullYear()} oVoxi · {BRAND.domain} · Pre-Seed · Confidential
        </p>
        <div className="flex items-center gap-6 text-xs text-slate-500">
          <span className="hover:text-slate-300 transition-colors cursor-default">Privacy</span>
          <span className="hover:text-slate-300 transition-colors cursor-default">Terms</span>
        </div>
      </div>
    </div>
  </footer>
);
