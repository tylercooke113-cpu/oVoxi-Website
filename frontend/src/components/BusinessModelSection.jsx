import React from 'react';
import { Reveal, SectionLabel } from './Reveal';
import { BUSINESS_MODEL } from '../content';

export const BusinessModelSection = () => (
  <section data-testid="business-model-section" className="relative bg-ink py-24 lg:py-32">
    <div className="mx-auto max-w-7xl px-6 lg:px-8">
      <Reveal className="max-w-3xl">
        <SectionLabel testid="business-model-label">Business Model</SectionLabel>
        <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          Catalog Licensing + Sync. Multiple Revenue Streams.
        </h2>
      </Reveal>

      <div className="mt-14 grid grid-cols-1 gap-6 md:grid-cols-3">
        {BUSINESS_MODEL.map((b, i) => (
          <Reveal key={b.title} delay={i * 0.1}>
            <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.02] p-8 transition-all duration-300 hover:-translate-y-1 hover:border-electric/40">
              <span className="w-fit rounded-full border border-electric/30 bg-electric/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-cyan">
                {b.tag}
              </span>
              <h3 className="mt-5 font-heading text-xl font-medium text-white">{b.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">{b.body}</p>
            </div>
          </Reveal>
        ))}
      </div>

      <Reveal delay={0.2}>
        <div className="mt-6 rounded-2xl border border-white/10 bg-gradient-to-br from-electric/[0.08] to-transparent p-8 md:p-10">
          <h3 className="font-heading text-lg font-medium text-white">Artist Economics</h3>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-400">
            Usage-based royalties pass directly to rights holders. oVoxi takes a licensing margin.
            Artists earn every time the catalog is used — attracting more talent and growing the
            catalog organically.
          </p>
        </div>
      </Reveal>
    </div>
  </section>
);
