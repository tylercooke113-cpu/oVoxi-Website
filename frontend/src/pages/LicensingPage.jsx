import React from 'react';
import { Check } from 'lucide-react';
import { PageHero } from '../components/PageHero';
import { Reveal, SectionLabel } from '../components/Reveal';
import { PrimaryCTA } from '../components/CtaButtons';
import { MarketSection } from '../components/MarketSection';
import { CompetitiveSection } from '../components/CompetitiveSection';
import { BusinessModelSection } from '../components/BusinessModelSection';
import { AI_BENEFITS } from '../content';

const LicensingPage = () => (
  <div data-testid="licensing-page">
    <PageHero
      testid="licensing-hero"
      label="AI & Enterprise Licensing"
      title="Train on Music You Can Actually License"
      subtitle="Fully cleared, ownership-verified, AI-ready catalogs with stems and clean metadata — built for AI music generators, ad agencies, game studios, and film & TV."
    />

    <section className="bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-16">
          <Reveal>
            <SectionLabel>Why Buyers Choose oVoxi</SectionLabel>
            <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Legally defensible audio, without the ambiguity.
            </h2>
            <ul className="mt-8 space-y-4">
              {AI_BENEFITS.map((b) => (
                <li key={b} className="flex items-start gap-3 text-base text-slate-300">
                  <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-electric/15 text-cyan">
                    <Check size={13} strokeWidth={3} />
                  </span>
                  {b}
                </li>
              ))}
            </ul>
            <div className="mt-10">
              <PrimaryCTA to="/contact?interest=ai_company" testid="licensing-page-cta">
                Discuss Licensing
              </PrimaryCTA>
            </div>
          </Reveal>

          <Reveal delay={0.12}>
            <div
              className="min-h-[320px] overflow-hidden rounded-2xl border border-white/10"
              style={{
                backgroundImage:
                  "url('https://images.unsplash.com/photo-1764258560300-2346b28b4e7c?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200')",
                backgroundSize: 'cover',
                backgroundPosition: 'center',
              }}
            />
          </Reveal>
        </div>
      </div>
    </section>

    <MarketSection />
    <BusinessModelSection />
    <CompetitiveSection />
  </div>
);

export default LicensingPage;
