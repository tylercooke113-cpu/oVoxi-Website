import { Link } from 'react-router-dom';
import { useMarketingPath } from '../MarketingPathContext';

export default function Close() {
  const { path } = useMarketingPath();

  return (
    <section className="py-24 md:py-40 border-t border-ovx-line">
      <div className="max-w-[1440px] mx-auto px-6 md:px-[120px]">
        <div className="flex flex-col sm:flex-row gap-4 mb-32">
          {(path === 'artists' || !path) && (
            <Link
              to="/apply"
              className="inline-block px-8 py-4 border border-ovx-cyan text-ovx-cyan font-body text-base hover:bg-ovx-cyan hover:text-black transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            >
              Start an application
            </Link>
          )}
          {(path === 'platforms' || !path) && (
            <Link
              to="/contact"
              className={[
                'inline-block px-8 py-4 font-body text-base transition-colors duration-150',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black',
                path === 'platforms'
                  ? 'border border-ovx-cyan text-ovx-cyan hover:bg-ovx-cyan hover:text-black'
                  : 'border border-ovx-line text-ovx-dim hover:border-ovx-cyan hover:text-ovx-cyan',
              ].join(' ')}
            >
              Request a sample pack
            </Link>
          )}
        </div>

        <footer className="border-t border-ovx-line pt-8 flex flex-col sm:flex-row justify-between items-start gap-6">
          <span className="font-jetmono text-[13px] text-ovx-faint uppercase tracking-[0.12em]">
            oVoxi
          </span>
          <div className="flex gap-8">
            <a
              href="mailto:hello@ovoxi.net"
              className="font-body text-sm text-ovx-faint hover:text-white transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            >
              Contact
            </a>
            <Link
              to="/contact"
              className="font-body text-sm text-ovx-faint hover:text-white transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
            >
              Legal
            </Link>
          </div>
        </footer>
      </div>
    </section>
  );
}
