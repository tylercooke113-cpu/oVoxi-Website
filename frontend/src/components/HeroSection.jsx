import React from 'react';
import Spline from '@splinetool/react-spline';
import { heroData } from '../data/mock';
import { ArrowRight } from 'lucide-react';

export const HeroSection = () => {
  return (
    <section className="relative min-h-screen bg-black pt-20 overflow-hidden">
      {/* Grid Pattern Overlay */}
      <div className="absolute inset-0 opacity-[0.03]">
        <div 
          className="w-full h-full"
          style={{
            backgroundImage: `
              linear-gradient(to right, white 1px, transparent 1px),
              linear-gradient(to bottom, white 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px'
          }}
        />
      </div>

      <div className="max-w-7xl mx-auto px-6 lg:px-8 relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 items-center min-h-[calc(100vh-80px)]">
          {/* Left Content */}
          <div className="flex flex-col justify-center py-20 lg:py-0">
            {/* Tagline */}
            <div className="inline-flex items-center gap-2 mb-6">
              <span className="w-8 h-[1px] bg-neon-blue"></span>
              <span className="text-neon-blue text-sm font-medium tracking-wider uppercase">
                {heroData.tagline}
              </span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-white leading-tight mb-6">
              {heroData.headline.split(':')[0]}:
              <span className="block text-neon-blue mt-2">
                {heroData.headline.split(':')[1]}
              </span>
            </h1>

            {/* Description */}
            <p className="text-gray-400 text-lg md:text-xl leading-relaxed mb-10 max-w-xl">
              {heroData.description}
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-4">
              <button className="group flex items-center justify-between gap-4 px-8 py-4 bg-neon-blue text-black font-medium text-lg hover:shadow-[0_0_30px_rgba(0,157,255,0.5)] transition-all duration-400">
                {heroData.primaryCTA}
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
              <button className="flex items-center justify-center gap-2 px-8 py-4 bg-white/10 text-white font-medium text-lg hover:bg-white hover:text-black transition-all duration-400">
                {heroData.secondaryCTA}
              </button>
            </div>
          </div>

          {/* Right - Spline 3D */}
          <div className="hidden lg:flex items-center justify-center relative">
            <div className="w-[700px] h-[700px] relative overflow-visible">
              <Spline 
                scene="https://prod.spline.design/NbVmy6DPLhY-5Lvg/scene.splinecode"
                className="w-full h-full"
              />
            </div>
            {/* Glow Effect */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-neon-blue/20 rounded-full blur-[100px] pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Bottom Gradient */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-black to-transparent" />
    </section>
  );
};
