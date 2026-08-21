import { useMarketingPath } from '../MarketingPathContext';

export default function Nav() {
  const { setPath } = useMarketingPath();

  const scrollTo = (id, pathChoice) => {
    setPath(pathChoice);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-ovx-line bg-black/80 backdrop-blur-sm">
      <div className="max-w-[1440px] mx-auto px-6 md:px-[120px] h-16 flex items-center justify-between">
        <span className="font-display font-extrabold text-white text-xl tracking-tight select-none">
          oVoxi
        </span>
        <div className="flex items-center gap-8">
          <button
            onClick={() => scrollTo('fork-section', 'platforms')}
            className="font-body text-sm text-ovx-dim hover:text-white transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
          >
            Platforms
          </button>
          <button
            onClick={() => scrollTo('fork-section', 'artists')}
            className="font-body text-sm text-ovx-dim hover:text-white transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
          >
            Artists
          </button>
        </div>
      </div>
    </nav>
  );
}
