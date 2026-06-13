import React from 'react';
import { HeroSection } from '../components/HeroSection';
import { SolutionSection } from '../components/SolutionSection';
import { WhyOvoxiSection } from '../components/WhyOvoxiSection';
import { AudienceSection } from '../components/AudienceSection';
import { FinalCTASection } from '../components/FinalCTASection';

const HomePage = () => (
  <div data-testid="home-page">
    <HeroSection />
    <SolutionSection />
    <WhyOvoxiSection />
    <AudienceSection />
    <FinalCTASection />
  </div>
);

export default HomePage;
