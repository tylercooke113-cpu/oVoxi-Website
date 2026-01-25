import React from 'react';
import { Shield, Brain, Scale, Database } from 'lucide-react';
import { featuresData } from '../data/mock';

const iconMap = {
  Shield: Shield,
  Brain: Brain,
  Scale: Scale,
  Database: Database
};

export const FeaturesSection = () => {
  return (
    <section className="relative py-32 bg-black">
      {/* Section Header */}
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-20">
          <span className="text-neon-blue text-sm font-medium tracking-wider uppercase mb-4 block">
            What We Do
          </span>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-6">
            The Infrastructure for
            <span className="text-neon-blue"> AI Audio Ethics</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Secure the legal chain and neural metadata required to build the future of synthetic audio with total confidence.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {featuresData.map((feature, index) => {
            const IconComponent = iconMap[feature.icon];
            return (
              <div
                key={feature.id}
                className="group relative p-8 bg-white/[0.02] border border-white/10 hover:border-neon-blue/50 transition-all duration-500"
              >
                {/* Number */}
                <span className="absolute top-6 right-6 text-5xl font-bold text-white/5 group-hover:text-neon-blue/10 transition-colors duration-500">
                  0{index + 1}
                </span>

                {/* Icon */}
                <div className="w-14 h-14 flex items-center justify-center bg-neon-blue/10 mb-6 group-hover:bg-neon-blue/20 transition-colors duration-300">
                  <IconComponent className="w-7 h-7 text-neon-blue" />
                </div>

                {/* Content */}
                <h3 className="text-xl font-semibold text-white mb-3">
                  {feature.title}
                </h3>
                <p className="text-gray-400 leading-relaxed">
                  {feature.description}
                </p>

                {/* Hover Line */}
                <div className="absolute bottom-0 left-0 w-0 h-[2px] bg-neon-blue group-hover:w-full transition-all duration-500" />
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
