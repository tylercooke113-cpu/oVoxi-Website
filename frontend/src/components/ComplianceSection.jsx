import React from 'react';
import { ShieldCheck, FileCheck, Lock } from 'lucide-react';
import { complianceData } from '../data/mock';

const iconMap = {
  'EU AI Act': ShieldCheck,
  'US NO FAKES Act': FileCheck,
  'GDPR': Lock
};

export const ComplianceSection = () => {
  return (
    <section id="compliance" className="relative py-32 bg-black">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 opacity-[0.02]">
        <div 
          className="w-full h-full"
          style={{
            backgroundImage: `
              linear-gradient(to right, white 1px, transparent 1px),
              linear-gradient(to bottom, white 1px, transparent 1px)
            `,
            backgroundSize: '80px 80px'
          }}
        />
      </div>

      <div className="max-w-7xl mx-auto px-6 lg:px-8 relative z-10">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-neon-blue text-sm font-medium tracking-wider uppercase mb-4 block">
            Compliance
          </span>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4">
            {complianceData.title}
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            {complianceData.subtitle}
          </p>
        </div>

        {/* Compliance Cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {complianceData.regulations.map((regulation, index) => {
            const IconComponent = iconMap[regulation.name];
            return (
              <div
                key={index}
                className="group relative p-8 bg-white/[0.02] border border-white/10 hover:border-neon-blue/50 transition-all duration-500 text-center"
              >
                {/* Icon */}
                <div className="w-16 h-16 flex items-center justify-center bg-neon-blue/10 mx-auto mb-6 group-hover:bg-neon-blue/20 transition-colors duration-300">
                  <IconComponent className="w-8 h-8 text-neon-blue" />
                </div>

                {/* Status Badge */}
                <div className="inline-flex items-center gap-2 px-3 py-1 bg-neon-blue/10 text-neon-blue text-xs font-medium uppercase tracking-wider mb-4">
                  <span className="w-2 h-2 bg-neon-blue rounded-full animate-pulse" />
                  {regulation.status}
                </div>

                {/* Content */}
                <h3 className="text-xl font-semibold text-white mb-3">
                  {regulation.name}
                </h3>
                <p className="text-gray-400 leading-relaxed">
                  {regulation.description}
                </p>
              </div>
            );
          })}
        </div>

        {/* Trust Statement */}
        <div className="mt-16 text-center">
          <p className="text-gray-500 text-lg">
            At oVoxi.ai, we secure the legal chain and neural metadata required to build the future of synthetic audio with <span className="text-white font-medium">total confidence</span>.
          </p>
        </div>
      </div>
    </section>
  );
};
