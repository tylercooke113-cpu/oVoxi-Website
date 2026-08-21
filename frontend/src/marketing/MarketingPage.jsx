import { useRef } from 'react';
import './styles/fonts.css';
import './styles/tokens.css';
import { MarketingPathProvider } from './MarketingPathContext';
import { ScrollProgressProvider } from './hooks/useScrollProgress';
import { useLenis } from './hooks/useLenis';
import Nav from './sections/Nav';
import Hero from './sections/Hero';
import Reckoning from './sections/Reckoning';
import Gate from './sections/Gate';
import Pipeline from './sections/Pipeline';
import Fork from './sections/Fork';
import Category from './sections/Category';
import Close from './sections/Close';

function MarketingContent() {
  const progressRef = useRef(0);
  useLenis(progressRef);

  return (
    <ScrollProgressProvider progressRef={progressRef}>
      <div className="bg-ovx-void min-h-screen text-white" data-marketing-page="">
        <Nav />
        <Hero />
        <Reckoning />
        <Gate />
        <Pipeline />
        <Fork />
        <Category />
        <Close />
      </div>
    </ScrollProgressProvider>
  );
}

export default function MarketingPage() {
  return (
    <MarketingPathProvider>
      <MarketingContent />
    </MarketingPathProvider>
  );
}
