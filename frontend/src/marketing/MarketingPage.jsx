import { useRef, lazy, Suspense } from 'react';
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

// Lazy: three.js stays out of the main bundle entirely
const Scene = lazy(() => import('./three/Scene'));

// Evaluated once at load time — not reactive, intentionally
const canRender3D = (() => {
  if (typeof window === 'undefined') return false;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
})();

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
      {/* z-[10] keeps DOM content above the fixed canvas */}
      <div className="relative z-[10] min-h-screen text-white" data-marketing-page="">
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
