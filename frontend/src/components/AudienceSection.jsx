import React from 'react';
import { Reveal, SectionLabel } from './Reveal';
import { PrimaryCTA } from './CtaButtons';
import { AI_COPY, ARTIST_COPY } from '../content';

export const AudienceSection = () => (
  <section data-testid="audience-section" className="relative border-y border-white/10 bg-ink py-24 lg:py-32">
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
              {AI_COPY.headline}
            </h3>
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
              {ARTIST_COPY.headline}
            </h3>
            <div className="mt-8">
              <PrimaryCTA to="/signup" testid="artists-section-cta">
                Join as an Artist
              </PrimaryCTA>
            </div>
          </div>
        </Reveal>
      </div>
    </div>
  </section>
);
