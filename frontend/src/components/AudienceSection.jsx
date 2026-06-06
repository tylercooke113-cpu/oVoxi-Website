import React from 'react';
import { Check } from 'lucide-react';
import { Reveal, SectionLabel } from './Reveal';
import { PrimaryCTA } from './CtaButtons';
import { AI_BENEFITS, ARTIST_BENEFITS } from '../content';

const BenefitList = ({ items }) => (
  <ul className="mt-6 space-y-3">
    {items.map((b) => (
      <li key={b} className="flex items-start gap-3 text-sm text-slate-300">
        <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-electric/15 text-cyan">
          <Check size={12} strokeWidth={3} />
        </span>
        {b}
      </li>
    ))}
  </ul>
);

export const AudienceSection = () => (
  <section data-testid="audience-section" className="relative border-y border-white/10 bg-ink-2 py-24 lg:py-32">
    <div className="mx-auto max-w-7xl px-6 lg:px-8">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Reveal>
          <div
            id="ai-companies"
            data-testid="ai-companies-card"
            className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.02] p-8 md:p-10"
          >
            <SectionLabel testid="ai-companies-label">For AI Companies</SectionLabel>
            <h3 className="font-heading text-2xl font-semibold text-white sm:text-3xl">
              Train on Music You Can Actually License
            </h3>
            <BenefitList items={AI_BENEFITS} />
            <div className="mt-8">
              <PrimaryCTA to="/contact?interest=ai_company" testid="ai-companies-cta">
                Discuss Licensing
              </PrimaryCTA>
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.12}>
          <div
            id="artists"
            data-testid="artists-card"
            className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.02] p-8 md:p-10"
          >
            <SectionLabel testid="artists-label">For Artists</SectionLabel>
            <h3 className="font-heading text-2xl font-semibold text-white sm:text-3xl">
              Turn Your Catalog Into Long-Term Licensing Revenue
            </h3>
            <BenefitList items={ARTIST_BENEFITS} />
            <div className="mt-8">
              <PrimaryCTA to="/contact?interest=artist" testid="artists-section-cta">
                Apply to Join
              </PrimaryCTA>
            </div>
          </div>
        </Reveal>
      </div>
    </div>
  </section>
);
