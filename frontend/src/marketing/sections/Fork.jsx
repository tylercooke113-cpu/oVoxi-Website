import { Link } from 'react-router-dom';
import { useMarketingPath } from '../MarketingPathContext';

const platformFeatures = [
  'Verified clearance',
  'Mastered audio + stems',
  'Structured metadata',
  'One agreement',
];

const artistFeatures = [
  'Mastering and stems, free',
  'You keep ownership',
  'Non-exclusive, always',
  'Founding Partner status',
];

function FeatureList({ items }) {
  return (
    <ul className="space-y-5 mt-8">
      {items.map((f) => (
        <li key={f} className="flex items-start gap-3">
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0 mt-[6px]"
            style={{ background: 'linear-gradient(135deg, #B44FD4 0%, #7B5EA7 50%, #6B7FD4 100%)' }}
            aria-hidden="true"
          />
          <span className="font-body text-ovx-dim" style={{ fontSize: 'var(--fs-body)' }}>
            {f}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function Fork() {
  const { path, setPath } = useMarketingPath();

  const platformsCollapsed = path === 'artists';
  const artistsCollapsed  = path === 'platforms';

  return (
    <section id="fork-section" className="py-24 md:py-40 border-t border-ovx-line">
      <div className="max-w-[1440px] mx-auto px-6 md:px-[120px]">
        <p className="font-jetmono text-[13px] uppercase tracking-[0.12em] bg-ovx-gradient bg-clip-text text-transparent mb-16">
          What you get
        </p>

        <div className="flex flex-col md:flex-row gap-px bg-ovx-line">
          {/* Platforms column */}
          <div
            className={[
              'bg-ovx-void p-8 md:p-12 transition-all duration-300',
              platformsCollapsed ? 'md:w-56 shrink-0' : 'flex-1',
            ].join(' ')}
          >
            {platformsCollapsed ? (
              <button
                onClick={() => setPath('platforms')}
                className="font-body text-ovx-faint hover:text-white transition-colors duration-150 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
              >
                For platforms &#8594;
              </button>
            ) : (
              <>
                <h3
                  className="font-display font-extrabold text-white leading-[0.95] tracking-[-0.02em]"
                  style={{ fontSize: 'var(--fs-h2)' }}
                >
                  For platforms
                </h3>
                <FeatureList items={platformFeatures} />
                <Link
                  to="/contact"
                  className="inline-block mt-10 px-6 py-3 border border-ovx-cyan text-ovx-cyan font-body text-sm hover:bg-ovx-cyan hover:text-black transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
                >
                  Request a sample pack
                </Link>
              </>
            )}
          </div>

          {/* Artists column */}
          <div
            className={[
              'bg-ovx-void p-8 md:p-12 transition-all duration-300',
              artistsCollapsed ? 'md:w-56 shrink-0' : 'flex-1',
            ].join(' ')}
          >
            {artistsCollapsed ? (
              <button
                onClick={() => setPath('artists')}
                className="font-body text-ovx-faint hover:text-white transition-colors duration-150 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
              >
                For artists &#8594;
              </button>
            ) : (
              <>
                <h3
                  className="font-display font-extrabold text-white leading-[0.95] tracking-[-0.02em]"
                  style={{ fontSize: 'var(--fs-h2)' }}
                >
                  For artists
                </h3>
                <FeatureList items={artistFeatures} />
                <Link
                  to="/apply"
                  className="inline-block mt-10 px-6 py-3 border border-ovx-cyan text-ovx-cyan font-body text-sm hover:bg-ovx-cyan hover:text-black transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-ovx-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-black"
                >
                  Start an application
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
