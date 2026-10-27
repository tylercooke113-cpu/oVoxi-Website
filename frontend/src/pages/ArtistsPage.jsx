import React from 'react';
import { Link } from 'react-router-dom';
import { ButtonLink } from '../landing/parts';
import { LINKS, buyerCta } from '../landing/links';
import useCatalogVisible from '../landing/useCatalogVisible';

// /artists (Direction C, "Artist-first", chosen Oct 27). Reached from "For artists" and
// "How it works"; every "Join as an artist" goes to sign-up.
const WRAP = 'mx-auto max-w-[1240px] px-6';

const STEPS = [
  ['Upload', 'Add your songs and splits. Pick sync, AI training or both.'],
  ['We prepare it', 'Mastering, stems and ownership checks. Co-writers sign online.'],
  ['Buyers license it', 'Creators, brands and AI teams find your music in the OVOXI Catalog.'],
  ['You get paid', 'Earnings land in your OVOXI Wallet and go to your bank monthly.'],
];

// Agreement 3.3 (rights kept; sync and AI training exclusive through OVOXI), 7.5 (PRO and
// mechanical income untouched), 7.4 and the Co-owner Consent (co-writers paid directly).
const FAQ = [
  ['Do I keep my rights?', 'Yes. You keep ownership, streaming, sales and your PRO royalties. OVOXI becomes the only place your chosen songs are licensed for sync and AI training.'],
  ['What does it cost?', 'Nothing to join. You earn a share of every license sold, set out in your agreement.'],
  ['What if I wrote it with someone?', 'Add them to the splits. They sign online and get paid their share directly.'],
  ['Can I take a song down?', 'Yes, from your Vault. Licenses already sold stay valid.'],
];

const ArtistsPage = () => {
  const buyer = buyerCta(useCatalogVisible());
  return (
    <div data-testid="artists-page" className="bg-ink pt-16 text-[#F4F4F6]">
      <section className={`${WRAP} flex flex-col gap-7 pb-24 pt-20 sm:pt-24`}>
        <p className="m-0 text-sm uppercase tracking-[0.14em] text-[#B44FD4]">For independent artists</p>
        <h1 className="m-0 max-w-[12ch] font-heading text-[48px] font-extrabold leading-[0.95] sm:text-[80px] lg:text-[104px]">
          Get paid when AI and brands use your music.
        </h1>
        <div className="flex flex-wrap items-end justify-between gap-8">
          <p className="m-0 max-w-[44ch] text-lg leading-relaxed text-[#A1A1AA] sm:text-[21px]">
            Upload once. We clear it, license it for sync and AI training, and pay you every month. You keep your
            streaming and PRO income.
          </p>
          <div className="flex flex-wrap gap-3">
            <ButtonLink to={LINKS.join} kind="artist" size="lg" testid="artists-join">Join as an artist</ButtonLink>
            <a href="#how" className="inline-flex items-center rounded-full border border-[#3F3F46] px-7 py-4 text-base font-bold text-[#F4F4F6] hover:bg-white/10">How it works</a>
          </div>
        </div>
      </section>

      <section id="how" className="border-t border-[#1F1F23]">
        <ol className={`${WRAP} m-0 grid list-none grid-cols-1 gap-10 py-24 sm:grid-cols-2 lg:grid-cols-4 lg:gap-0`}>
          {STEPS.map(([title, text], i) => (
            <li key={title} className={`flex flex-col gap-3 lg:px-6 ${i === 0 ? 'lg:pl-0' : ''} ${i < 3 ? 'lg:border-r lg:border-[#1F1F23]' : 'lg:pr-0'}`}>
              <span className={`font-heading text-[56px] font-extrabold leading-none ${i === 3 ? 'text-[#B44FD4]' : 'text-[#52525B]'}`}>{i + 1}</span>
              <h2 className="m-0 font-heading text-2xl font-bold">{title}</h2>
              <p className="m-0 text-base leading-relaxed text-[#A1A1AA]">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-label="Your Wallet" className={`${WRAP} pb-24`}>
        <div className="flex flex-wrap items-center gap-10 rounded-3xl border border-[#27272A] bg-[#0E0E12] p-8 sm:p-10">
          <div className="flex min-w-0 flex-[1_1_380px] flex-col gap-3.5">
            <h2 className="m-0 font-heading text-[32px] font-extrabold leading-tight sm:text-[36px]">See every sale. Every month.</h2>
            <p className="m-0 text-[17px] leading-relaxed text-[#A1A1AA]">
              Your Wallet shows what each song earned and when it pays out. Co-writers get their own share, paid directly.
            </p>
          </div>
          <div aria-hidden="true" className="grid min-w-0 flex-[1_1_420px] grid-cols-2 gap-3">
            <div className="rounded-2xl bg-[#18181B] p-5">
              <p className="m-0 text-xs uppercase tracking-[0.1em] text-[#A1A1AA]">Earned this month</p>
              <p className="m-0 mt-1.5 font-heading text-[28px] font-extrabold">$—</p>
            </div>
            <div className="rounded-2xl bg-[#18181B] p-5">
              <p className="m-0 text-xs uppercase tracking-[0.1em] text-[#A1A1AA]">Payouts</p>
              <p className="m-0 mt-1.5 font-heading text-[28px] font-extrabold">Monthly</p>
            </div>
            <div className="col-span-2 flex justify-between gap-3 rounded-2xl bg-[#18181B] px-5 py-4 text-[15px]">
              <span>Your song · Sync license</span><span className="font-bold text-[#E9D5FF]">$—</span>
            </div>
          </div>
        </div>
      </section>

      <section id="faq" className="mx-auto flex max-w-[880px] flex-col px-6 pb-24">
        <h2 className="m-0 mb-4 font-heading text-[36px] font-extrabold sm:text-[40px]">Straight answers</h2>
        {FAQ.map(([q, a], i) => (
          <details key={q} className={`border-t border-[#27272A] py-5 ${i === FAQ.length - 1 ? 'border-b' : ''}`}>
            <summary className="cursor-pointer text-[19px] font-bold">{q}</summary>
            <p className="m-0 mt-3 text-base leading-relaxed text-[#A1A1AA]">{a}</p>
          </details>
        ))}
      </section>

      <section className="border-t border-[#1F1F23] bg-[#0B0B0E]">
        <div className={`${WRAP} flex flex-col items-center gap-6 py-24 text-center`}>
          <h2 className="m-0 font-heading text-[40px] font-extrabold leading-none sm:text-[72px]">Your next fan might be a brand.</h2>
          <ButtonLink to={LINKS.join} kind="artist" size="lg">Join as an artist</ButtonLink>
        </div>
      </section>

      <section className={`${WRAP} flex flex-wrap items-center justify-between gap-4 py-12`}>
        <p className="m-0 text-[17px] text-[#D4D4D8]">Looking to license music for a project or for AI training?</p>
        <span className="flex flex-wrap gap-5 font-bold">
          <Link to={buyer.to} className="text-cyan hover:underline">{buyer.label}</Link>
          <Link to={LINKS.ai} className="text-cyan hover:underline">Talk to sales</Link>
        </span>
      </section>
    </div>
  );
};

export default ArtistsPage;
