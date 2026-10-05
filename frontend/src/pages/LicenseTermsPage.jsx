import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { syncApi } from '../sync/api';

// Public License Terms page (Brief 18), same dark style as Privacy and Terms.
export default function LicenseTermsPage() {
  const [blocks, setBlocks] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    syncApi.terms('v1').then((d) => setBlocks(d.blocks)).catch(() => setError(true));
  }, []);

  return (
    <div className="min-h-screen bg-ink px-6 pt-24 pb-20">
      <div className="mx-auto max-w-3xl">
        <h1 className="font-heading text-3xl font-semibold text-white">oVoxi Music License Terms</h1>
        {error && <p className="mt-6 text-sm text-slate-400">Could not load the terms. Please try again.</p>}
        {!blocks && !error && <Loader2 className="mt-8 animate-spin text-electric" size={28} />}
        {blocks && (
          <div className="mt-6 space-y-3 text-sm leading-relaxed text-slate-300">
            {blocks.map((b, i) => {
              if (b.type === 'title') return null;  // the page already shows the title as H1
              if (b.type === 'heading') return <h2 key={i} className="pt-3 font-heading text-lg font-semibold text-white">{b.text}</h2>;
              if (b.type === 'item') return <p key={i} className="pl-5">{b.text}</p>;
              return <p key={i}>{b.text}</p>;
            })}
          </div>
        )}
      </div>
    </div>
  );
}
