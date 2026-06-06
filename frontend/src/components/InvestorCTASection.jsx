import React from 'react';
import { Reveal } from './Reveal';
import { PrimaryCTA, GhostCTA } from './CtaButtons';

export const InvestorCTASection = () => (
  <section data-testid="investor-cta-section" className="relative overflow-hidden bg-ink py-28 lg:py-36">
    <div className="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-electric/15 blur-[160px]" />
    <div className="absolute inset-0 grid-bg opacity-30" />

    <div className="relative mx-auto max-w-3xl px-6 text-center lg:px-8">
      <Reveal>
        <p className="text-xs font-bold uppercase tracking-[0.25em] text-electric">Pre-Seed · 2026</p>
        <h2 className="mt-5 font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          Building the Infrastructure Layer for Licensed AI Music
        </h2>
        <p className="mt-6 text-base leading-relaxed text-slate-400 sm:text-lg">
          The next wave of AI audio is coming. The catalog that captures emerging artists first
          defines what AI music sounds like.
        </p>
        <div className="mt-10 flex flex-col justify-center gap-3 sm:flex-row">
          <PrimaryCTA to="/contact?interest=investor" testid="investor-inquiries-cta">
            Investor Inquiries
          </PrimaryCTA>
          <GhostCTA to="/investors" testid="investor-overview-cta">
            View Investor Overview
          </GhostCTA>
        </div>
      </Reveal>
    </div>
  </section>
);
