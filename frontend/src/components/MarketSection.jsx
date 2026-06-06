import React from 'react';
import { Bot, Building2, Clapperboard, Gamepad2, Megaphone } from 'lucide-react';
import { Reveal, SectionLabel } from './Reveal';
import { MARKETS } from '../content';

const ICONS = { Bot, Building2, Clapperboard, Gamepad2, Megaphone };

export const MarketSection = () => (
  <section data-testid="market-section" className="relative border-y border-white/10 bg-ink-2 py-24 lg:py-32">
    <div
      className="absolute inset-0 opacity-[0.18]"
      style={{
        backgroundImage:
          "url('https://images.pexels.com/photos/8640331/pexels-photo-8640331.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940')",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    />
    <div className="absolute inset-0 bg-gradient-to-b from-ink-2 via-ink-2/80 to-ink-2" />

    <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
      <Reveal className="max-w-3xl">
        <SectionLabel testid="market-label">Market Opportunity</SectionLabel>
        <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          A $6.6B Market With No Emerging-First Catalog Layer
        </h2>
        <p className="mt-5 text-base leading-relaxed text-slate-400 sm:text-lg">
          Demand spans every buyer that needs legally defensible, culturally fresh audio — and grows
          9× to $60B by 2034.
        </p>
      </Reveal>

      <div className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {MARKETS.map((m, i) => {
          const Icon = ICONS[m.icon];
          return (
            <Reveal key={m.title} delay={i * 0.08}>
              <div className="flex h-full items-start gap-4 rounded-2xl border border-white/10 bg-ink/60 p-7 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:border-electric/40">
                <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-electric/10 ring-1 ring-electric/30">
                  <Icon size={20} className="text-cyan" />
                </span>
                <div>
                  <h3 className="font-heading text-lg font-medium text-white">{m.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{m.body}</p>
                </div>
              </div>
            </Reveal>
          );
        })}
      </div>
    </div>
  </section>
);
