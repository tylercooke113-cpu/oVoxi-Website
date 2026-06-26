import React from 'react';
import { PageHero } from '../components/PageHero';
import { Reveal, SectionLabel } from '../components/Reveal';
import { PrimaryCTA, GhostCTA } from '../components/CtaButtons';
import { BRAND } from '../content';

const PILLARS = [
  { title: 'Emerging-First', body: 'We acquire artists and sounds 12–18 months before mainstream recognition — capturing cultural relevance competitors cannot replicate in hindsight.' },
  { title: 'Fully Licensed', body: 'PRO registration, in-house chain-of-title verification, and documented ownership at ingestion. Every asset is clearable, every deal closeable.' },
  { title: 'AI-Ready', body: 'Broadcast-grade masters, stems as standard, and clean metadata — purpose-built for AI training, generation, and enterprise sync.' },
];

const AboutPage = () => (
  <div data-testid="about-page">
    <PageHero
      testid="about-hero"
      title="A Licensed Music Infrastructure Company for the AI Era"
      subtitle="oVoxi is building the world's first emerging-first, fully licensed, AI-ready music catalog — the provenance and licensing layer the generative music economy is missing."
    />

    <section className="border-y border-white/10 bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <Reveal className="text-center">
          <SectionLabel>What We Stand For</SectionLabel>
          <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Three pillars. One catalog.
          </h2>
        </Reveal>
        <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
          {PILLARS.map((p, i) => (
            <Reveal key={p.title} delay={i * 0.1}>
              <div className="h-full rounded-2xl border border-white/10 bg-white/[0.02] p-8 transition-all duration-300 hover:-translate-y-1 hover:border-electric/40">
                <h3 className="font-heading text-xl font-medium text-white">{p.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{p.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>

  </div>
);

export default AboutPage;
