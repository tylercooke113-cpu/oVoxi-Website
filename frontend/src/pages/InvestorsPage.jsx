import React from 'react';
import { Check } from 'lucide-react';
import { PageHero } from '../components/PageHero';
import { Reveal, SectionLabel } from '../components/Reveal';
import { PrimaryCTA } from '../components/CtaButtons';
import { RoadmapSection } from '../components/RoadmapSection';
import { STATS, USE_OF_FUNDS, TRACTION } from '../content';

const MILESTONES = [
  '500+ artist catalog at 12 months',
  'First AI platform deal signed',
  'Stems library fully built',
  'Seed-ready by Q2 2027',
];

const InvestorsPage = () => (
  <div data-testid="investors-page">
    <PageHero
      testid="investors-hero"
      label="Pre-Seed · 2026"
      title="Building the Infrastructure Layer for Licensed AI Music"
      subtitle="oVoxi is raising a pre-seed SAFE round to acquire the emerging-first catalog that defines what AI music sounds like."
    />

    {/* The Ask */}
    <section className="bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-3">
          <Reveal>
            <div className="rounded-2xl border border-electric/30 bg-gradient-to-br from-electric/[0.12] to-transparent p-8 md:p-10">
              <SectionLabel>The Ask</SectionLabel>
              <div className="font-heading text-5xl font-semibold text-white lg:text-6xl">$350K</div>
              <p className="mt-3 text-sm text-slate-400">Pre-Seed SAFE Round</p>
              <div className="mt-8">
                <PrimaryCTA to="/contact?interest=investor" testid="investors-page-cta">
                  Investor Inquiries
                </PrimaryCTA>
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.1} className="lg:col-span-2">
            <SectionLabel>Use of Funds</SectionLabel>
            <div className="mt-2 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {USE_OF_FUNDS.map((f) => (
                <div
                  key={f.title}
                  className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 transition-all duration-300 hover:border-electric/40"
                >
                  <div className="font-heading text-2xl font-semibold text-electric">{f.pct}</div>
                  <h3 className="mt-2 font-heading text-base font-medium text-white">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.body}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </div>
    </section>

    {/* Market stats */}
    <section className="border-y border-white/10 bg-ink-2 py-16">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-8 lg:grid-cols-4">
          {STATS.map((s, i) => (
            <Reveal key={s.value} delay={i * 0.08}>
              <div className="text-center lg:text-left">
                <div className="font-heading text-3xl font-semibold text-white lg:text-4xl">{s.value}</div>
                <p className="mt-2 text-sm text-slate-400">{s.label}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>

    {/* Traction + milestones */}
    <section className="bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-16">
          <Reveal>
            <SectionLabel>Current Traction</SectionLabel>
            <h2 className="font-heading text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              A working foundation, already in motion.
            </h2>
            <ul className="mt-8 space-y-4">
              {TRACTION.map((t) => (
                <li key={t} className="flex items-start gap-3 text-base text-slate-300">
                  <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-electric/15 text-cyan">
                    <Check size={13} strokeWidth={3} />
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={0.12}>
            <SectionLabel>Target Milestones</SectionLabel>
            <div className="mt-2 space-y-4">
              {MILESTONES.map((m, i) => (
                <div
                  key={m}
                  className="flex items-center gap-4 rounded-2xl border border-white/10 bg-white/[0.02] p-5"
                >
                  <span className="font-heading text-lg font-semibold text-electric">0{i + 1}</span>
                  <span className="text-base text-slate-200">{m}</span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </div>
    </section>

    <RoadmapSection />
  </div>
);

export default InvestorsPage;
