import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { ButtonLink, Check, Eyebrow } from '../landing/parts';
import { LINKS } from '../landing/links';

// Custom Datasets homepage (Plan 29, copy draft v2, approved Nov 8).
// Copy rules: no studio names, no sample pack, no counts except the network line,
// no prices, deposits, reply times or artist pay.
const WRAP = 'mx-auto max-w-[1200px] px-6';
const H2 = 'm-0 font-heading text-[32px] font-extrabold leading-[1.08] sm:text-[44px]';
const CARD = 'flex flex-col gap-3 rounded-[20px] border border-[#27272A] bg-[#111114] p-8';
const CARD_TITLE = 'm-0 text-[22px] font-bold';
const BODY = 'm-0 text-[17px] leading-relaxed text-[#A1A1AA]';
const PURPLE = 'text-[#C78BE0]';

const TRUST = ['Never released', 'True multitracks', 'Consent on every file', 'Exclusivity available'];

const GAP = [
  ['Already released', 'Catalog music is already out in the world. Other buyers can license the same tracks.'],
  ['Mostly stereo', 'Catalogs usually ship finished mixes. Stems, when offered, are often separated by software after the fact.'],
  ['Freelancers take managing', 'Hiring producers one at a time means tracking consent, ownership and quality yourself.'],
];

const DELIVERABLES = [
  'Full mixes',
  'True multitracks, printed from the session',
  'MIDI and tempo maps',
  'Lyrics with timestamps',
  'Chord, key and instrument labels',
  'A provenance manifest for every file',
  'A dataset card for the delivery',
];

const STEPS = [
  ["Tell us what's missing", 'Genre, language, instruments, vocal style, tempo, track count, format and labels.'],
  ['Get a scope', 'We send a statement of work and a schedule.'],
  ['We cast it', 'Writers, artists, producers and session players from our network of over 2,000 artists and producers.'],
  ['We record to protocol', 'Every session follows one standard for mics, channels, file naming, sample rate, click and stem printing.'],
  ['Everyone signs in the room', 'Composers, master owners, session players and vocalists, including a voice and likeness release.'],
  ['We check and label it', 'Originality checks, technical QC and annotation.'],
  ['We deliver', 'Securely, with an optional exclusivity window of 6, 12 or 24 months.'],
];

const WHY = [
  ['Never released', 'Recorded for your project, not pulled from a catalog.'],
  ['Exclusive if you want it', 'Sole training rights for 6, 12 or 24 months.'],
  ['Documented consent', 'Composer, master and performer sign-off on every file, recorded in a provenance manifest.'],
  ['Real multitracks', 'Printed from the session, not separated by software.'],
  ['One protocol', 'Every session is recorded to the same standard in commercial studios.'],
  ['Shaped by your evals', 'Tell us where your model falls short and we record to close the gap.'],
];

const WAYS = [
  ['Custom commission', 'Tracks made to your spec, with annotations.'],
  ['Exclusive window', 'A custom commission with sole training rights for 6, 12 or 24 months.'],
  ['Evaluation sets', 'Small, never-released sets for testing your models.'],
];

const HomePage = () => {
  const { hash } = useLocation();

  // "How it works" in the header links to /#how. Scroll after the route's
  // scroll-to-top has run, hence the animation frame.
  useEffect(() => {
    if (hash !== '#how') return undefined;
    const id = requestAnimationFrame(() => {
      const el = document.getElementById('how');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    return () => cancelAnimationFrame(id);
  }, [hash]);

  return (
    <div data-testid="home-page" className="bg-ink pt-16 font-light text-[#F4F4F6]">
      {/* Hero */}
      <section className={`${WRAP} flex flex-col items-center gap-7 pb-[104px] pt-24 text-center sm:pt-[120px]`}>
        <p className="m-0 text-sm font-medium uppercase tracking-[0.14em] text-cyan">Custom music datasets for AI</p>
        <h1 className="m-0 max-w-[16ch] font-heading text-[40px] font-extrabold leading-[1.02] sm:text-[64px] lg:text-[84px]">
          The music data your model needs doesn&apos;t exist yet. We record it.
        </h1>
        <p className="m-0 max-w-[54ch] text-lg leading-relaxed text-[#A1A1AA] sm:text-[21px]">
          OVOXI makes custom datasets for AI labs: new, never-released music recorded to your spec in commercial
          studios, with true multitracks and signed consent from everyone in the room.
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-5">
          <ButtonLink to={LINKS.request} kind="artist" size="lg" testid="home-request">Request data</ButtonLink>
          <a href="#how" data-testid="home-how" className="text-base font-medium text-[#D4D4D8] underline-offset-4 hover:underline">
            See how it works
          </a>
        </div>
      </section>

      {/* Trust bar */}
      <section aria-label="At a glance" className="border-y border-[#1F1F23]">
        <ul className={`${WRAP} m-0 grid list-none grid-cols-1 gap-5 py-7 text-base font-normal text-[#D4D4D8] sm:grid-cols-2 lg:grid-cols-4`}>
          {TRUST.map((t) => <li key={t} className="flex items-center gap-2.5"><Check />{t}</li>)}
        </ul>
      </section>

      {/* The gap */}
      <section className={`${WRAP} flex flex-col gap-10 py-28`}>
        <div className="flex flex-col gap-4">
          <Eyebrow color={PURPLE}>The gap</Eyebrow>
          <h2 className={H2}>Licensed catalogs are open to everyone.</h2>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {GAP.map(([t, b]) => (
            <div key={t} className={CARD}><h3 className={CARD_TITLE}>{t}</h3><p className={BODY}>{b}</p></div>
          ))}
        </div>
      </section>

      {/* What you get */}
      <section className="border-y border-[#1F1F23] bg-[#0B0B0E]">
        <div className={`${WRAP} grid grid-cols-1 items-start gap-14 py-28 md:grid-cols-2`}>
          <div className="flex flex-col gap-4">
            <Eyebrow color="text-cyan">What you get</Eyebrow>
            <h2 className={H2}>Delivered ready for training.</h2>
          </div>
          <ul className="m-0 flex list-none flex-col p-0 text-[19px] font-normal text-[#E4E4E7]">
            {DELIVERABLES.map((d, i) => (
              <li key={d} className={`border-t border-[#27272A] py-4 ${i === DELIVERABLES.length - 1 ? 'border-b' : ''}`}>{d}</li>
            ))}
          </ul>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className={`${WRAP} flex scroll-mt-20 flex-col gap-12 py-28`}>
        <div className="flex flex-col gap-4">
          <Eyebrow color={PURPLE}>How it works</Eyebrow>
          <h2 className={H2}>From spec to delivery.</h2>
        </div>
        <ol className="m-0 grid list-none grid-cols-1 gap-x-8 gap-y-10 p-0 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(([t, b], i) => (
            <li key={t} className="flex flex-col gap-2.5 border-t border-[#27272A] pt-5">
              <span className="font-heading text-[40px] font-extrabold leading-none text-[#52525B]">{`0${i + 1}`}</span>
              <h3 className="m-0 text-[21px] font-bold">{t}</h3>
              <p className="m-0 text-base leading-relaxed text-[#A1A1AA]">{b}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Why OVOXI */}
      <section className="border-y border-[#1F1F23] bg-[#0B0B0E]">
        <div className={`${WRAP} flex flex-col gap-12 py-28`}>
          <div className="flex flex-col gap-4">
            <Eyebrow color="text-cyan">Why OVOXI</Eyebrow>
            <h2 className={H2}>Made for your model.</h2>
          </div>
          <div className="grid grid-cols-1 gap-x-12 gap-y-10 md:grid-cols-2 lg:grid-cols-3">
            {WHY.map(([t, b]) => (
              <div key={t} className="flex flex-col gap-2"><h3 className="m-0 text-[21px] font-bold">{t}</h3><p className={BODY}>{b}</p></div>
            ))}
          </div>
        </div>
      </section>

      {/* Ways to work with us */}
      <section className={`${WRAP} flex flex-col gap-10 py-28`}>
        <h2 className={H2}>Ways to work with us.</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {WAYS.map(([t, b]) => (
            <div key={t} className={CARD}><h3 className={CARD_TITLE}>{t}</h3><p className={BODY}>{b}</p></div>
          ))}
        </div>
        <div><ButtonLink to={LINKS.request} kind="artist">Request data</ButtonLink></div>
      </section>

      {/* Artist strip */}
      <section className="border-t border-[#1F1F23]">
        <div className={`${WRAP} flex flex-wrap items-center justify-between gap-4 py-10`}>
          <p className="m-0 text-[19px] font-normal text-[#D4D4D8]">Make music? Record sessions for AI labs.</p>
          <ButtonLink to={LINKS.artists} kind="ghost" testid="home-artists">Join the network</ButtonLink>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-[#1F1F23] bg-[#0B0B0E]">
        <div className={`${WRAP} flex flex-col items-center gap-8 py-[120px] text-center`}>
          <h2 className="m-0 max-w-[16ch] font-heading text-[36px] font-extrabold leading-[1.04] sm:text-[64px]">
            Tell us what your model is missing.
          </h2>
          <ButtonLink to={LINKS.request} kind="artist" size="lg">Request data</ButtonLink>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
