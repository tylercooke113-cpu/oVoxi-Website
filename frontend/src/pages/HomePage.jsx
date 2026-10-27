import React from 'react';
import { Link } from 'react-router-dom';
import { ButtonLink, Check, Eyebrow } from '../landing/parts';
import { LINKS, buyerCta } from '../landing/links';
import useCatalogVisible from '../landing/useCatalogVisible';

// The landing page (Direction A, "Two doors", chosen Oct 27): one door for artists, one for
// buyers, AI teams one link below. Copy is short on purpose.
const WRAP = 'mx-auto max-w-[1200px] px-6';
const H2 = 'm-0 font-heading text-[36px] font-extrabold leading-[1.08] sm:text-[44px]';

const Steps = ({ color, items }) => (
  <ol className="m-0 flex list-none flex-col gap-4 p-0 text-[17px] leading-relaxed text-[#D4D4D8]">
    {items.map((t, i) => (
      <li key={t} className="flex gap-4">
        <span className={`font-heading font-extrabold ${color}`}>{`0${i + 1}`}</span>{t}
      </li>
    ))}
  </ol>
);

const TRUST = ['Ownership checked on every track', 'Every co-writer signs', 'Stems available', 'License you can verify online'];

const HomePage = () => {
  const buyer = buyerCta(useCatalogVisible());
  return (
    <div data-testid="home-page" className="bg-ink pt-16 text-[#F4F4F6]">
      <section className={`${WRAP} flex flex-col items-center gap-6 pb-[72px] pt-20 text-center sm:pt-24`}>
        <p className="m-0 text-sm uppercase tracking-[0.14em] text-cyan">Licensed music for media and AI</p>
        <h1 className="m-0 max-w-[15ch] font-heading text-[40px] font-extrabold leading-[1.02] sm:text-[64px] lg:text-[80px]">
          Music that&apos;s cleared. Artists who get paid.
        </h1>
        <p className="m-0 max-w-[46ch] text-lg leading-relaxed text-[#A1A1AA] sm:text-xl">
          Original music from independent artists, licensed to brands, creators and AI companies. Every owner signs.
          Every sale pays.
        </p>

        <div className="mt-6 grid w-full max-w-[880px] grid-cols-1 gap-4 text-left md:grid-cols-2">
          <div className="flex flex-col gap-3 rounded-[20px] border border-[#27272A] bg-[#111114] p-8" data-testid="door-artist">
            <Eyebrow color="text-[#B44FD4]">I make music</Eyebrow>
            <h2 className="m-0 font-heading text-[28px] font-bold leading-tight">Earn from sync and AI licensing</h2>
            <p className="m-0 text-base leading-relaxed text-[#A1A1AA]">Upload, we handle the rest. Paid monthly.</p>
            <div className="mt-2 flex flex-wrap items-center gap-4">
              <ButtonLink to={LINKS.join} kind="artist" arrow testid="home-join">Join as an artist</ButtonLink>
              <Link to={LINKS.artists} data-testid="home-artists-how" className="text-[15px] font-medium text-[#D4D4D8] underline-offset-4 hover:underline">How it works</Link>
            </div>
          </div>
          <div className="flex flex-col gap-3 rounded-[20px] border border-[#27272A] bg-[#111114] p-8" data-testid="door-buyer">
            <Eyebrow color="text-cyan">I need music</Eyebrow>
            <h2 className="m-0 font-heading text-[28px] font-bold leading-tight">License tracks in minutes</h2>
            <p className="m-0 text-base leading-relaxed text-[#A1A1AA]">For videos, ads, films, games and apps.</p>
            <div className="mt-2">
              <ButtonLink to={buyer.to} kind="buyer" arrow testid="home-buyer">{buyer.label}</ButtonLink>
            </div>
          </div>
        </div>
        <p className="m-0 mt-1 text-[15px] text-[#A1A1AA]">
          Training AI models? <Link to={LINKS.ai} data-testid="home-ai" className="text-cyan hover:underline">Talk to us about licensed data</Link>
        </p>
      </section>

      <section aria-label="Why it&apos;s safe to license" className="border-y border-[#1F1F23]">
        <ul className={`${WRAP} m-0 grid list-none grid-cols-1 gap-5 py-7 text-[15px] text-[#D4D4D8] sm:grid-cols-2 lg:grid-cols-4`}>
          {TRUST.map((t) => <li key={t} className="flex items-center gap-2.5"><Check />{t}</li>)}
        </ul>
      </section>

      <section className={`${WRAP} grid grid-cols-1 gap-12 py-24 md:grid-cols-2`}>
        <div className="flex flex-col gap-5">
          <Eyebrow color="text-[#B44FD4]">For artists</Eyebrow>
          <h2 className={H2}>Your songs, working while you make the next one.</h2>
          <Steps color="text-[#B44FD4]" items={[
            'Upload your tracks and choose sync, AI training or both.',
            'We master, split stems and clear ownership.',
            'Buyers license your music. Your Wallet pays out monthly.',
          ]} />
          <div className="flex flex-wrap items-center gap-4">
            <ButtonLink to={LINKS.join} kind="artist">Join as an artist</ButtonLink>
            <Link to={LINKS.artists} className="text-[15px] font-medium text-[#D4D4D8] underline-offset-4 hover:underline">How it works</Link>
          </div>
        </div>
        <div className="flex flex-col gap-5">
          <Eyebrow color="text-cyan">For buyers</Eyebrow>
          <h2 className={H2}>Fresh music, no clearance headaches.</h2>
          <Steps color="text-cyan" items={[
            'Search by mood, genre and BPM. Preview anything.',
            'Buy a single license or subscribe.',
            'Download the track, stems and your license certificate.',
          ]} />
          <div><ButtonLink to={buyer.to} kind="buyer">{buyer.label}</ButtonLink></div>
        </div>
      </section>

      <section className="border-y border-[#1F1F23] bg-[#0B0B0E]">
        <div className={`${WRAP} flex flex-wrap items-center justify-between gap-8 py-20`}>
          <div className="flex min-w-0 flex-[1_1_520px] flex-col gap-4">
            <Eyebrow>For AI teams</Eyebrow>
            <h2 className="m-0 font-heading text-[34px] font-extrabold leading-tight sm:text-[40px]">Training data with a paper trail.</h2>
            <p className="m-0 max-w-[52ch] text-lg leading-relaxed text-[#A1A1AA]">
              Consented, rights-cleared music with stems and metadata. Every track traces back to signed agreements.
            </p>
          </div>
          <ButtonLink to={LINKS.ai} kind="ghost">Talk to sales</ButtonLink>
        </div>
      </section>

      <section className={`${WRAP} flex flex-col items-center gap-6 pb-28 pt-24 text-center`}>
        <h2 className="m-0 max-w-[18ch] font-heading text-[36px] font-extrabold leading-[1.05] sm:text-[60px]">Make music? Need music? Start here.</h2>
        <div className="flex flex-wrap justify-center gap-3">
          <ButtonLink to={LINKS.join} kind="artist" size="lg">Join as an artist</ButtonLink>
          <ButtonLink to={buyer.to} kind="buyer" size="lg">{buyer.label}</ButtonLink>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
