import React from 'react';
import { ArrowRight, Check } from 'lucide-react';
import { forCreatorsData, forAILabsData } from '../data/mock';

export const AudienceSection = () => {
  return (
    <section className="relative py-32 bg-black">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-8">
          {/* For Creators Card */}
          <div 
            id="creators"
            className="group relative p-10 lg:p-12 bg-white/[0.02] border border-white/10 hover:border-neon-blue/30 transition-all duration-500"
          >
            {/* Background Glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-neon-blue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            
            <div className="relative z-10">
              <span className="text-neon-blue text-sm font-medium tracking-wider uppercase">
                {forCreatorsData.title}
              </span>
              <h3 className="text-2xl md:text-3xl font-bold text-white mt-3 mb-4">
                {forCreatorsData.subtitle}
              </h3>
              <p className="text-gray-400 leading-relaxed mb-8">
                {forCreatorsData.description}
              </p>

              {/* Benefits */}
              <ul className="space-y-4 mb-10">
                {forCreatorsData.benefits.map((benefit, index) => (
                  <li key={index} className="flex items-center gap-3">
                    <div className="w-5 h-5 flex items-center justify-center bg-neon-blue/20">
                      <Check className="w-3 h-3 text-neon-blue" />
                    </div>
                    <span className="text-gray-300">{benefit}</span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <button className="group/btn flex items-center gap-3 px-6 py-3 bg-neon-blue text-black font-medium hover:shadow-[0_0_20px_rgba(0,157,255,0.4)] transition-all duration-300">
                {forCreatorsData.cta}
                <ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" />
              </button>
            </div>
          </div>

          {/* For AI Labs Card */}
          <div 
            id="ai-labs"
            className="group relative p-10 lg:p-12 bg-white/[0.02] border border-white/10 hover:border-neon-blue/30 transition-all duration-500"
          >
            {/* Background Glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-neon-blue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            
            <div className="relative z-10">
              <span className="text-neon-blue text-sm font-medium tracking-wider uppercase">
                {forAILabsData.title}
              </span>
              <h3 className="text-2xl md:text-3xl font-bold text-white mt-3 mb-4">
                {forAILabsData.subtitle}
              </h3>
              <p className="text-gray-400 leading-relaxed mb-8">
                {forAILabsData.description}
              </p>

              {/* Benefits */}
              <ul className="space-y-4 mb-10">
                {forAILabsData.benefits.map((benefit, index) => (
                  <li key={index} className="flex items-center gap-3">
                    <div className="w-5 h-5 flex items-center justify-center bg-neon-blue/20">
                      <Check className="w-3 h-3 text-neon-blue" />
                    </div>
                    <span className="text-gray-300">{benefit}</span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <button className="group/btn flex items-center gap-3 px-6 py-3 bg-white/10 text-white font-medium hover:bg-white hover:text-black transition-all duration-300">
                {forAILabsData.cta}
                <ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
