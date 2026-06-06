import React from 'react';
import { motion } from 'framer-motion';

// Lightweight scroll-reveal wrapper used across sections.
export const Reveal = ({ children, delay = 0, className = '', y = 24 }) => (
  <motion.div
    className={className}
    initial={{ opacity: 0, y }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true, margin: '-80px' }}
    transition={{ duration: 0.6, delay, ease: [0.21, 0.47, 0.32, 0.98] }}
  >
    {children}
  </motion.div>
);

export const SectionLabel = ({ children, testid }) => (
  <span
    data-testid={testid}
    className="inline-block text-xs tracking-[0.25em] uppercase font-bold text-electric mb-5"
  >
    {children}
  </span>
);
