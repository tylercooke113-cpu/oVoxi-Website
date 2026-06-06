import React from 'react';
import { Reveal, SectionLabel } from './Reveal';
import { STATS, PROBLEMS } from '../content';

export const ProblemSection = () => (
  <section data-testid="problem-section" className="relative bg-ink py-24 lg:py-32">
    <div className="mx-auto max-w-7xl px-6 lg:px-8">
      <Reveal>
        <SectionLabel testid="problem-label">The Problem</SectionLabel>
        <h2 className="max-w-3xl font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          AI Generators Are Hungry.<br />
          <span className="text-slate-500">The Legal Content Doesn&apos;t Exist.</span>
        </h2>
      </Reveal>

      <div className="mt-14 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] lg:grid-cols-4">
        {STATS.map((s, i) => (
          <Reveal key={s.value} delay={i * 0.08}>
            <div className="h-full bg-ink p-7 lg:p-9">
              <div className="font-heading text-3xl font-semibold text-white lg:text-4xl">
                {s.value}
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">{s.label}</p>
            </div>
          </Reveal>
        ))}
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
        {PROBLEMS.map((p, i) => (
          <Reveal key={p.title} delay={i * 0.1}>
            <div className="h-full rounded-2xl border border-white/10 bg-white/[0.02] p-8 transition-all duration-300 hover:-translate-y-1 hover:border-electric/40">
              <h3 className="font-heading text-xl font-medium text-white">{p.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">{p.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
);
