import React from 'react';
import { HeroSection } from '../components/HeroSection';
import { ProblemSection } from '../components/ProblemSection';
import { SolutionSection } from '../components/SolutionSection';
import { WhyOvoxiSection } from '../components/WhyOvoxiSection';
import { MarketSection } from '../components/MarketSection';
import { CompetitiveSection } from '../components/CompetitiveSection';
import { AudienceSection } from '../components/AudienceSection';
import { BusinessModelSection } from '../components/BusinessModelSection';
import { RoadmapSection } from '../components/RoadmapSection';
import { InvestorCTASection } from '../components/InvestorCTASection';

const HomePage = () => (
  <div data-testid="home-page">
    <HeroSection />
    <ProblemSection />
    <SolutionSection />
    <WhyOvoxiSection />
    <MarketSection />
    <CompetitiveSection />
    <AudienceSection />
    <BusinessModelSection />
    <RoadmapSection />
    <InvestorCTASection />
  </div>
);

export default HomePage;
