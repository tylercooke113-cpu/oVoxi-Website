import React from 'react';
import { Check, Music2, Sparkles, FileCheck2, Layers } from 'lucide-react';
import { PageHero } from '../components/PageHero';
import { Reveal, SectionLabel } from '../components/Reveal';
import { PrimaryCTA } from '../components/CtaButtons';
import { ARTIST_BENEFITS } from '../content';

const PILLARS = [
  { icon: FileCheck2, title: 'PRO Registration', body: 'Every artist registered with ASCAP, BMI, or SESAC — handled entirely by us. Automated at onboarding, zero friction.' },
  { icon: Sparkles, title: 'In-House Mastering', body: 'Every track mastered to broadcast standard. Clean, normalized audio trains AI models better and increases per-asset value.' },
  { icon: Layers, title: 'Stems Delivery', body: 'Stems are required alongside masters. AI platforms pay 2–3× more for them. We build it in from day one.' },
  { icon: Music2, title: 'Ownership Verification', body: 'Our in-house chain-of-title system documents every split and rights holder at ingestion. No ambiguous ownership.' },
];

const ArtistsPage = () => (
  <div data-testid="artists-page">
    <PageHero
      testid="artists-hero"
      label="For Artists"
      title="Turn Your Music Into Licensing Revenue"
      subtitle="oVoxi is the only catalog company built exclusively for emerging artists. We prepare your music for AI platforms and enterprise clients — and pay you when it licenses."
    />

    <section className="bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-3xl px-6 text-center lg:px-8">
          <Reveal>
            <SectionLabel>What You Get</SectionLabel>
            <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Built for the artist, end to end.
            </h2>
            <ul className="mt-8 mx-auto w-fit space-y-4">
              {ARTIST_BENEFITS.map((b) => (
                <li key={b} className="flex items-start gap-3 text-base text-slate-300">
                  <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-electric/15 text-cyan">
                    <Check size={13} strokeWidth={3} />
                  </span>
                  {b}
                </li>
              ))}
            </ul>
            <div className="mt-10">
              <PrimaryCTA to="https://airtable.com/appmcBnXvP82ydQCz/pag6udQiv3QTWYG3m/form" testid="artists-page-apply-cta">
                Apply to Join
              </PrimaryCTA>
            </div>
          </Reveal>
      </div>
    </section>

    <section className="border-t border-white/10 bg-ink-2 py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <Reveal className="max-w-3xl">
          <SectionLabel>How We Build The Catalog</SectionLabel>
          <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            We Remove Every Barrier Between Artists and Licensing Revenue
          </h2>
        </Reveal>
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2">
          {PILLARS.map((p, i) => (
            <Reveal key={p.title} delay={i * 0.08}>
              <div className="flex h-full items-start gap-4 rounded-2xl border border-white/10 bg-white/[0.02] p-7 transition-all duration-300 hover:-translate-y-1 hover:border-electric/40">
                <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-electric/10 ring-1 ring-electric/30">
                  <p.icon size={20} className="text-cyan" />
                </span>
                <div>
                  <h3 className="font-heading text-lg font-medium text-white">{p.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{p.body}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  </div>
);

export default ArtistsPage;
