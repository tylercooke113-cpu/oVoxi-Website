import React from 'react';
import { statsData } from '../data/mock';

export const StatsSection = () => {
  return (
    <section className="relative py-20 bg-black border-y border-white/10">
      <div className="max-w-5xl mx-auto px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-16">
          {statsData.map((stat, index) => (
            <div
              key={index}
              className="text-center group"
            >
              <div className="text-4xl md:text-5xl lg:text-6xl font-bold text-neon-blue mb-2 group-hover:scale-105 transition-transform duration-300">
                {stat.value}
              </div>
              <div className="text-gray-400 text-sm md:text-base font-medium uppercase tracking-wider">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
