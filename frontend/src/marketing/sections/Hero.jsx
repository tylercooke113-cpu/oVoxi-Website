import { useMarketingPath } from '../MarketingPathContext';
import { Reveal } from '../components/Reveal';

export default function Hero() {
  const { setPath } = useMarketingPath();

  const handleFork = (choice) => {
    setPath(choice);
    document.getElementById('fork-section')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section className="relative min-h-screen flex flex-col justify-center pt-16 py-24 md:py-40">
      <div className="max-w-[1440px] mx-auto px-6 md:px-[120px] w-full">
        <Reveal delay={0}>
          <h1
            className="font-display font-extrabold text-white leading-[0.95] tracking-[-0.02em] mb-8"
            style={{ fontSize: 'var(--fs-hero)' }}
          >
            Emerging-First.<br />
            Fully Licensed.<br />
            AI-Ready.
          </h1>
        </Reveal>
        <Reveal delay={0.1}>
          <p
            className="font-body text-ovx-dim mb-12 max-w-xl"
            style={{ fontSize: 'var(--fs-lead)' }}
          >
            The curated music catalog built for AI platforms and enterprise buyers.
          </p>
        </Reveal>
        <Reveal delay={0.2}>
          <div className="flex flex-col sm:flex-row gap-4">
            <button
              onClick={() => handleFork('platforms')}
              className="inline-flex items-center justify-between gap-6 border border-ovx-line text-white hover:border-ovx-cyan hover:text-ovx-cyan focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black px-8 py-4 transition-colors duration-150 font-body text-base"
            >
              I license music <span aria-hidden="true">&#8594;</span>
            </button>
            <button
              onClick={() => handleFork('artists')}
              className="inline-flex items-center justify-between gap-6 border border-ovx-line text-white hover:border-ovx-cyan hover:text-ovx-cyan focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black px-8 py-4 transition-colors duration-150 font-body text-base"
            >
              I make music <span aria-hidden="true">&#8594;</span>
            </button>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
