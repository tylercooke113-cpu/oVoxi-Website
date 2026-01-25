import React from 'react';
import { ArrowRight } from 'lucide-react';

export const CTASection = () => {
  return (
    <section className="relative py-32 bg-black overflow-hidden">
      {/* Background Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-neon-blue/10 rounded-full blur-[150px] pointer-events-none" />
      
      <div className="max-w-4xl mx-auto px-6 lg:px-8 relative z-10">
        <div className="text-center">
          {/* Headline */}
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-6">
            Ready to Build the Future of
            <span className="block text-neon-blue mt-2">Ethical AI Music?</span>
          </h2>
          
          <p className="text-gray-400 text-lg md:text-xl max-w-2xl mx-auto mb-10">
            Whether you're an artist looking to license your digital identity or a startup seeking audit-ready training data, oVoxi.ai is the standard for responsible machine intelligence.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button className="group flex items-center justify-center gap-3 px-8 py-4 bg-neon-blue text-black font-medium text-lg hover:shadow-[0_0_30px_rgba(0,157,255,0.5)] transition-all duration-400">
              Start Building Today
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <button className="flex items-center justify-center gap-2 px-8 py-4 bg-white/10 text-white font-medium text-lg hover:bg-white hover:text-black transition-all duration-400">
              Contact Sales
            </button>
          </div>

          {/* Trust Text */}
          <p className="mt-8 text-gray-500 text-sm">
            Join 1000+ creators and 50+ AI labs already using oVoxi.ai
          </p>
        </div>
      </div>
    </section>
  );
};
