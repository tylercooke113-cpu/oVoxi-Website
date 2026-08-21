import './styles/fonts.css';
import './styles/tokens.css';
import { MarketingPathProvider } from './MarketingPathContext';
import Nav from './sections/Nav';
import Hero from './sections/Hero';
import Reckoning from './sections/Reckoning';
import Gate from './sections/Gate';
import Pipeline from './sections/Pipeline';
import Fork from './sections/Fork';
import Category from './sections/Category';
import Close from './sections/Close';

export default function MarketingPage() {
  return (
    <MarketingPathProvider>
      <div className="bg-ovx-void min-h-screen text-white">
        <Nav />
        <Hero />
        <Reckoning />
        <Gate />
        <Pipeline />
        <Fork />
        <Category />
        <Close />
      </div>
    </MarketingPathProvider>
  );
}
