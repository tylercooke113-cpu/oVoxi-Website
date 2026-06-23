import React, { useState } from 'react';
import { Music2, Sparkles, FileCheck2, Layers } from 'lucide-react';
import { PageHero } from '../components/PageHero';
import { Reveal, SectionLabel } from '../components/Reveal';
import { PrimaryCTA } from '../components/CtaButtons';
import { ARTIST_BENEFITS } from '../content';
import ParticleHero from '../components/ParticleHero';

const BENEFITS_CARDS = [
  { num: '01', title: 'PRO Registration', description: 'Handled for you at no cost. Your rights, properly registered from day one.' },
  { num: '02', title: 'Professional Mastering', description: 'Delivered via LANDR. Industry-standard quality that platforms require.' },
  { num: '03', title: '4-Stem Separation', description: 'Vocals, drums, bass, melody — delivered to AI platforms in the format they need.' },
  { num: '04', title: 'Chain-of-Title', description: 'Fingerprinting and documentation that makes your catalog enterprise-grade.' },
  { num: '05', title: 'Licensing Revenue', description: 'Every time your music is used. Paid directly. No label cut.' },
  { num: '06', title: 'No Upfront Cost', description: 'We only win when you win. Zero cost to apply or onboard.' },
];

function BenefitCard({ num, title, description }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative',
        backgroundColor: hovered ? '#060606' : '#000000',
        padding: '26px 22px',
        transition: 'background 0.2s',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: 2,
          background: 'linear-gradient(180deg, #C2185B, #6A1B9A)',
          opacity: hovered ? 1 : 0,
          transition: 'opacity 0.3s',
        }}
      />
      <span
        style={{
          display: 'block',
          fontFamily: "'Syne', system-ui, sans-serif",
          fontWeight: 800,
          fontSize: '11px',
          letterSpacing: '0.15em',
          background: 'linear-gradient(90deg, #C2185B, #6A1B9A)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          marginBottom: '10px',
        }}
      >
        {num}
      </span>
      <h3
        style={{
          fontFamily: "'Syne', system-ui, sans-serif",
          fontWeight: 700,
          fontSize: '17px',
          color: '#ffffff',
          margin: '0 0 6px',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontFamily: "'DM Sans', system-ui, sans-serif",
          fontWeight: 300,
          fontSize: '13px',
          color: '#666',
          lineHeight: 1.6,
          margin: 0,
        }}
      >
        {description}
      </p>
    </div>
  );
}

const PILLARS = [
  { icon: FileCheck2, title: 'PRO Registration', body: 'Every artist registered with ASCAP, BMI, or SESAC — handled entirely by us. Automated at onboarding, zero friction.' },
  { icon: Sparkles, title: 'In-House Mastering', body: 'Every track mastered to broadcast standard. Clean, normalized audio trains AI models better and increases per-asset value.' },
  { icon: Layers, title: 'Stems Delivery', body: 'Stems are required alongside masters. AI platforms pay 2–3× more for them. We build it in from day one.' },
  { icon: Music2, title: 'Ownership Verification', body: 'Our in-house chain-of-title system documents every split and rights holder at ingestion. No ambiguous ownership.' },
];

const ArtistsPage = () => (
  <div data-testid="artists-page">
    <ParticleHero />

    <section className="bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-3xl px-6 text-center lg:px-8 mb-12">
        <Reveal>
          <SectionLabel>What You Get</SectionLabel>
          <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Built for the artist, end to end.
          </h2>
        </Reveal>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '1px',
          backgroundColor: '#1a1a1a',
        }}
      >
        {BENEFITS_CARDS.map((b) => (
          <BenefitCard key={b.num} {...b} />
        ))}
      </div>
      <div className="mt-10 text-center">
        <PrimaryCTA to="https://airtable.com/appmcBnXvP82ydQCz/pag6udQiv3QTWYG3m/form" testid="artists-page-apply-cta">
          Apply to Join
        </PrimaryCTA>
      </div>
    </section>

    <section className="border-t border-white/10 bg-ink py-20 lg:py-28">
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
