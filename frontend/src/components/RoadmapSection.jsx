import React from 'react';
import { Reveal, SectionLabel } from './Reveal';
import { ROADMAP } from '../content';

export const RoadmapSection = () => (
  <section data-testid="roadmap-section" className="relative border-y border-white/10 bg-ink-2 py-24 lg:py-32">
    <div className="mx-auto max-w-7xl px-6 lg:px-8">
      <Reveal className="max-w-3xl">
        <SectionLabel testid="roadmap-label">Traction & Roadmap</SectionLabel>
        <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          Working Foundation. Clear Path to First Revenue.
        </h2>
      </Reveal>

      <div className="relative mt-16">
        <div className="absolute left-0 right-0 top-5 hidden h-px bg-gradient-to-r from-electric/60 via-electric/30 to-transparent lg:block" />
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-4">
          {ROADMAP.map((r, i) => (
            <Reveal key={r.quarter} delay={i * 0.1}>
              <div className="relative">
                <span className="relative z-10 mb-6 inline-flex h-3 w-3 rounded-full bg-electric shadow-[0_0_14px_rgba(0,102,255,0.8)]" />
                <div className="rounded-2xl border border-white/10 bg-ink/60 p-6 backdrop-blur-sm">
                  <span className="text-xs font-bold uppercase tracking-[0.2em] text-cyan">
                    {r.quarter}
                  </span>
                  <h3 className="mt-3 font-heading text-lg font-medium text-white">{r.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{r.body}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </div>
  </section>
);
