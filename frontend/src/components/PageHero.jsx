import React from 'react';
import { motion } from 'framer-motion';

// Compact hero used at the top of inner pages.
export const PageHero = ({ label, title, subtitle, testid }) => (
  <section
    data-testid={testid}
    className="relative overflow-hidden border-b border-white/10 bg-ink pt-36 pb-16 lg:pt-44 lg:pb-24"
  >
    <div className="absolute inset-0 grid-bg opacity-30" />
    <div className="absolute -top-24 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-electric/15 blur-[140px]" />
    <div className="relative mx-auto max-w-4xl px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        {label && (
          <span className="text-xs font-bold uppercase tracking-[0.25em] text-electric">{label}</span>
        )}
        <h1 className="mt-4 font-heading text-4xl font-semibold leading-[1.05] tracking-tighter text-white sm:text-5xl lg:text-6xl">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-400 sm:text-lg">
            {subtitle}
          </p>
        )}
      </motion.div>
    </div>
  </section>
);
