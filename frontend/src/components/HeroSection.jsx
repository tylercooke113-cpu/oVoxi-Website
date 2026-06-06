import React from 'react';
import { motion } from 'framer-motion';
import { HeroCanvas } from './HeroCanvas';
import { PrimaryCTA, GhostCTA } from './CtaButtons';
import { BRAND } from '../content';

export const HeroSection = () => (
  <section data-testid="hero-section" className="relative min-h-[100svh] overflow-hidden bg-ink">
    <HeroCanvas />
    {/* Readability overlays */}
    <div className="absolute inset-0 grid-bg opacity-40" />
    <div className="absolute inset-0 bg-gradient-to-b from-ink/70 via-ink/40 to-ink" />
    <div className="absolute -top-40 left-1/2 h-[480px] w-[480px] -translate-x-1/2 rounded-full bg-electric/20 blur-[160px]" />

    <div className="relative z-10 mx-auto flex min-h-[100svh] max-w-5xl flex-col items-center justify-center px-6 pt-24 text-center lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mb-7 flex flex-wrap items-center justify-center gap-2"
      >
        {BRAND.pillars.map((p) => (
          <span
            key={p}
            className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-1.5 text-xs font-medium text-slate-300"
          >
            {p}
          </span>
        ))}
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.1 }}
        className="font-heading text-4xl font-semibold leading-[1.05] tracking-tighter text-white sm:text-5xl lg:text-7xl"
      >
        The Curated Music Catalog
        <span className="block text-gradient-blue">for the AI Generation</span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.25 }}
        className="mt-7 max-w-2xl text-base leading-relaxed text-slate-400 sm:text-lg"
      >
        oVoxi delivers emerging-first, fully licensed, AI-ready music catalogs built for AI training,
        content generation, sync licensing, and enterprise media.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.4 }}
        className="mt-10 flex flex-col gap-3 sm:flex-row"
      >
        <PrimaryCTA to="/contact?interest=ai_company" testid="hero-partnership-cta">
          Request Partnership
        </PrimaryCTA>
        <GhostCTA to="/artists" testid="hero-artist-cta">
          Join as an Artist
        </GhostCTA>
      </motion.div>
    </div>

    <div className="pointer-events-none absolute bottom-0 inset-x-0 h-24 bg-gradient-to-t from-ink to-transparent" />
  </section>
);
