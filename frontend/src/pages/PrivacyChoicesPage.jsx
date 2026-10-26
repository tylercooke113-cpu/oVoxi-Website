import React from 'react';
import { Link } from 'react-router-dom';
import { PageHero } from '../components/PageHero';
import PrivacyChoicesPanel from '../privacy/PrivacyChoicesPanel';
import { gpcOn } from '../lib/consent';

// "Do Not Sell or Share My Personal Information" (Privacy Policy section 6), linked from
// every footer. Works signed out (this visit) and signed in (the account).
const PrivacyChoicesPage = () => (
  <div data-testid="privacy-choices-page">
    <PageHero testid="privacy-choices-hero" label="Privacy" title="Do Not Sell or Share My Personal Information" />
    <section className="bg-ink py-16 lg:py-20">
      <div className="mx-auto max-w-2xl space-y-6 px-6 text-base leading-relaxed text-slate-400 lg:px-8">
        <p>
          Turn off the first switch to opt out of OVOXI selling or sharing your personal information, as
          described in section 6 of our <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link>.
          The second switch controls analytics and session replay, described in
          our <Link to="/data-policy" className="text-cyan hover:underline">Data Collection Policy</Link>.
        </p>
        {gpcOn() && (
          <p className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300" data-testid="choices-gpc">
            Your browser sends a Global Privacy Control signal, so we treat it as a request to opt out of
            selling and sharing. This stays off while the signal is on.
          </p>
        )}
        <PrivacyChoicesPanel source="privacy_choices" />
      </div>
    </section>
  </div>
);

export default PrivacyChoicesPage;
