import React, { useState } from 'react';
import { PageHero } from '../components/PageHero';
import { Reveal, SectionLabel } from '../components/Reveal';
import { PrimaryCTA } from '../components/CtaButtons';

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
          background: 'linear-gradient(180deg, #B44FD4, #7B5EA7)',
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
          background: 'linear-gradient(90deg, #B44FD4, #7B5EA7)',
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

const ArtistsPage = () => (
  <div data-testid="artists-page">
    <PageHero
      testid="artists-hero"
      label="For Emerging Artists"
      title="Turn Your Music Into Licensing Revenue."
      subtitle="oVoxi is the only catalog company built exclusively for emerging artists. We prepare your music for AI platforms — and pay you when it licenses."
      centered={true}
    />

    <section className="bg-ink pt-10 pb-20 lg:pt-14 lg:pb-28">
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
        <PrimaryCTA to="/signup" testid="artists-page-apply-cta">
          Join as an Artist
        </PrimaryCTA>
      </div>
    </section>
  </div>
);

export default ArtistsPage;
