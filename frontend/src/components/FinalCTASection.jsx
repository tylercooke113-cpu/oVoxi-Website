import React from 'react';
import { Reveal } from './Reveal';
import { PrimaryCTA, GhostCTA } from './CtaButtons';

export const FinalCTASection = () => (
  <section data-testid="final-cta-section" className="relative overflow-hidden bg-ink py-28 lg:py-36">
    <div className="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-electric/15 blur-[160px]" />
    <div className="absolute inset-0 grid-bg opacity-30" />

    <div className="relative mx-auto max-w-3xl px-6 text-center lg:px-8">
      <Reveal>
        <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          The AI Music Economy Is Here. Get Your Catalog Inside It.
        </h2>
        <p className="mt-6 text-base leading-relaxed text-slate-400 sm:text-lg">
          oVoxi is actively building its founding catalog. Emerging artists accepted now.
        </p>
        <div className="mt-10 flex flex-col justify-center gap-3 sm:flex-row">
          <PrimaryCTA to="https://airtable.com/appmcBnXvP82ydQCz/pag6udQiv3QTWYG3m/form" testid="final-artist-cta">
            Apply as a Founding Artist
          </PrimaryCTA>
          <GhostCTA to="/contact?interest=ai_company" testid="final-licensing-cta">
            Discuss Licensing
          </GhostCTA>
        </div>
      </Reveal>
    </div>
  </section>
);
