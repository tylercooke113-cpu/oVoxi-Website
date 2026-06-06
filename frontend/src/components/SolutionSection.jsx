import React from 'react';
import { ArrowRight } from 'lucide-react';
import { Reveal, SectionLabel } from './Reveal';
import { PROCESS } from '../content';

export const SolutionSection = () => (
  <section data-testid="solution-section" className="relative border-y border-white/10 bg-ink-2 py-24 lg:py-32">
    <div className="absolute inset-0 grid-bg opacity-30" />
    <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
      <Reveal className="max-w-3xl">
        <SectionLabel testid="solution-label">The Solution</SectionLabel>
        <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          The Emerging Artist Catalog Built for AI Licensing
        </h2>
        <p className="mt-5 text-base leading-relaxed text-slate-400 sm:text-lg">
          One vertically integrated pipeline turns raw, emerging talent into fully cleared,
          AI-ready licensing assets.
        </p>
      </Reveal>

      <div className="mt-16">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          {PROCESS.map((p, i) => (
            <Reveal key={p.step} delay={i * 0.1}>
              <div className="group relative h-full rounded-2xl border border-white/10 bg-white/[0.02] p-8 transition-all duration-300 hover:-translate-y-1 hover:border-electric/40">
                <div className="flex items-center justify-between">
                  <span className="font-heading text-4xl font-semibold text-electric/30 transition-colors group-hover:text-electric/70">
                    {p.step}
                  </span>
                  {i < PROCESS.length - 1 && (
                    <ArrowRight size={18} className="hidden text-slate-600 lg:block" />
                  )}
                </div>
                <h3 className="mt-5 font-heading text-lg font-medium text-white">{p.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{p.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </div>
  </section>
);
