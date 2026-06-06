import React from 'react';
import { Check, Minus } from 'lucide-react';
import { Reveal, SectionLabel } from './Reveal';
import { COMPETITORS, COMPARISON } from '../content';

const Cell = ({ active, highlight }) => (
  <div className="flex items-center justify-center">
    {active ? (
      <span
        className={`inline-flex h-7 w-7 items-center justify-center rounded-full ${
          highlight ? 'bg-electric text-white shadow-[0_0_16px_rgba(0,102,255,0.6)]' : 'bg-white/10 text-slate-300'
        }`}
      >
        <Check size={15} strokeWidth={3} />
      </span>
    ) : (
      <Minus size={16} className="text-slate-700" />
    )}
  </div>
);

export const CompetitiveSection = () => (
  <section data-testid="competitive-section" className="relative bg-ink py-24 lg:py-32">
    <div className="mx-auto max-w-7xl px-6 lg:px-8">
      <Reveal className="max-w-3xl">
        <SectionLabel testid="competitive-label">Competitive Landscape</SectionLabel>
        <h2 className="font-heading text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
          Everyone Has Catalogs. Nobody Has Tomorrow&apos;s Sound.
        </h2>
      </Reveal>

      <Reveal delay={0.1}>
        <div className="mt-14 overflow-x-auto rounded-2xl border border-white/10">
          <table data-testid="comparison-table" className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="bg-white/[0.03]">
                <th className="p-5 text-xs font-bold uppercase tracking-[0.15em] text-slate-500">
                  Capability
                </th>
                {COMPETITORS.map((c) => (
                  <th key={c} className="p-5 text-center text-sm font-medium text-slate-400">
                    {c}
                  </th>
                ))}
                <th className="p-5 text-center text-sm font-semibold text-white bg-electric/10">
                  oVoxi
                </th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row) => (
                <tr key={row.feature} className="border-t border-white/10">
                  <td className="p-5 text-sm font-medium text-slate-200">{row.feature}</td>
                  {row.values.slice(0, 3).map((v, idx) => (
                    <td key={idx} className="p-5">
                      <Cell active={v} />
                    </td>
                  ))}
                  <td className="p-5 bg-electric/[0.06]">
                    <Cell active={row.values[3]} highlight />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>
    </div>
  </section>
);
