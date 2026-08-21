import { useRef, lazy, Suspense } from 'react';
import './styles/fonts.css';
import './styles/tokens.css';
import { MarketingPathProvider } from './MarketingPathContext';
import { ScrollProgressProvider } from './hooks/useScrollProgress';
import { useLenis } from './hooks/useLenis';
import { canRender3D } from './hooks/useCanRender3D';
import Nav from './sections/Nav';
import Hero from './sections/Hero';
import Reckoning from './sections/Reckoning';
import Gate from './sections/Gate';
import Pipeline from './sections/Pipeline';
import Fork from './sections/Fork';
import Category from './sections/Category';
import Close from './sections/Close';

// Lazy: three.js stays out of the main bundle entirely
const Scene = lazy(() => import('./three/Scene'));

function MarketingContent() {
  const progressRef = useRef(0);
  useLenis(progressRef);

  return (
    <ScrollProgressProvider progressRef={progressRef}>
      {canRender3D && (
        <Suspense fallback={null}>
          <Scene />
        </Suspense>
      )}
      {/* bg-black ensures page is always black even when canvas is skipped */}
      <div className="relative z-[10] min-h-screen text-white bg-black" data-marketing-page="">
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
