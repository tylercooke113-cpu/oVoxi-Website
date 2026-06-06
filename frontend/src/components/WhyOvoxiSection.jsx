import React from 'react';
import { Sparkles, ShieldCheck, Layers, Coins, Cpu } from 'lucide-react';
import { Reveal, SectionLabel } from './Reveal';
import { WHY } from '../content';

const ICONS = { Sparkles, ShieldCheck, Layers, Coins, Cpu };

export const WhyOvoxiSection = () => (
  <section data-testid="why-section" className="relative bg-ink py-24 lg:py-32">
    <div className="mx-auto max-w-7xl px-6 lg:px-8">
      <Reveal className="max-w-3xl">
        <SectionLabel testid="why-label">Why oVoxi</SectionLabel>
        <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          The Infrastructure Advantage
        </h2>
        <p className="mt-5 text-base leading-relaxed text-slate-400 sm:text-lg">
          Five structural advantages competitors cannot reverse-engineer after the fact.
        </p>
      </Reveal>

      <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {WHY.map((w, i) => {
          const Icon = ICONS[w.icon];
          const wide = i === 0 ? 'lg:col-span-2' : '';
          return (
            <Reveal key={w.title} delay={i * 0.08} className={wide}>
              <div className="group h-full rounded-2xl border border-white/10 bg-white/[0.02] p-8 transition-all duration-300 hover:-translate-y-1 hover:border-electric/40 hover:shadow-[0_0_40px_rgba(0,102,255,0.12)]">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-electric/10 ring-1 ring-electric/30">
                  <Icon size={20} className="text-cyan" />
                </span>
                <h3 className="mt-5 font-heading text-xl font-medium text-white">{w.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{w.body}</p>
              </div>
            </Reveal>
          );
        })}
      </div>
    </div>
  </section>
);
