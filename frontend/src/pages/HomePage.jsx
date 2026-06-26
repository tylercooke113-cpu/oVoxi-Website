import React from 'react';
import { HeroSection } from '../components/HeroSection';
import { SolutionSection } from '../components/SolutionSection';
import { AudienceSection } from '../components/AudienceSection';
import { FinalCTASection } from '../components/FinalCTASection';
import WaveformSection from '../components/WaveformSection';

const HomePage = () => (
  <div data-testid="home-page">
    <HeroSection />
    <SolutionSection />
    <AudienceSection />
    <FinalCTASection />
    <WaveformSection />
  </div>
);

export default HomePage;
