import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { navigationLinks } from '../data/mock';

const AIRTABLE_ARTIST_INFO = "https://airtable.com/appmcBnXvP82ydQCz/pag6udQiv3QTWYG3m/form";

export const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-black border-b border-white/10">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <a href="/" className="flex items-center gap-2">
            <span className="text-2xl font-bold text-white">
              oVoxi<span className="text-neon-blue">.ai</span>
            </span>
          </a>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-8">
            {navigationLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-gray-400 hover:text-white transition-colors duration-300 text-sm font-medium"
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center gap-4">
            <a 
              href={AIRTABLE_ARTIST_INFO}
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 bg-neon-blue text-black font-medium hover:bg-neon-blue/90 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,157,255,0.4)]"
            >
              Get Started
            </a>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden text-white p-2"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden py-4 border-t border-white/10">
            <nav className="flex flex-col gap-4">
              {navigationLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-gray-400 hover:text-white transition-colors duration-300 text-sm font-medium py-2"
                  onClick={() => setIsMenuOpen(false)}
                >
                  {link.label}
                </a>
              ))}
              <a 
                href={AIRTABLE_ARTIST_INFO}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 px-6 py-3 bg-neon-blue text-black font-medium hover:bg-neon-blue/90 transition-all duration-300 text-center"
              >
                Get Started
              </a>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
};
