import React from 'react';

export const Footer = () => {
  return (
    <footer className="relative bg-black border-t border-white/10">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-16">
        <div className="text-center">
          {/* Logo */}
          <a href="/" className="inline-block mb-6">
            <span className="text-3xl font-bold text-white">
              oVoxi<span className="text-neon-blue">.ai</span>
            </span>
          </a>
          
          {/* Tagline */}
          <p className="text-gray-300 text-lg mb-4">
            The Ethical Architecture for Generative Sound
          </p>
          
          {/* Description */}
          <p className="text-gray-500 text-sm max-w-md mx-auto">
            The world's first high-fidelity provenance layer for the AI music era.
          </p>
        </div>
      </div>
    </footer>
  );
};
