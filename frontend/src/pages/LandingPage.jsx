import React from 'react';
import { Header } from '../components/Header';
import { HeroSection } from '../components/HeroSection';
import { FeaturesSection } from '../components/FeaturesSection';
import { StatsSection } from '../components/StatsSection';
import { AudienceSection } from '../components/AudienceSection';
import { ComplianceSection } from '../components/ComplianceSection';
import { CTASection } from '../components/CTASection';
import { Footer } from '../components/Footer';

const LandingPage = () => {
  return (
    <div className="min-h-screen bg-black">
      <Header />
      <main>
        <HeroSection />
        <StatsSection />
        <FeaturesSection />
        <AudienceSection />
        <ComplianceSection />
        <CTASection />
      </main>
      <Footer />
    </div>
  );
};

export default LandingPage;
