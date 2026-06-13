import React from 'react';
import { HeroSection } from '../components/HeroSection';
import { ProblemSection } from '../components/ProblemSection';
import { SolutionSection } from '../components/SolutionSection';
import { WhyOvoxiSection } from '../components/WhyOvoxiSection';
import { AudienceSection } from '../components/AudienceSection';
import { FinalCTASection } from '../components/FinalCTASection';

const HomePage = () => (
  <div data-testid="home-page">
    <HeroSection />
    <ProblemSection />
    <SolutionSection />
    <WhyOvoxiSection />
    <AudienceSection />
    <FinalCTASection />
  </div>
);

export default HomePage;
