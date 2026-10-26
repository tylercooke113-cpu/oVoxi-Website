import React from 'react';
import { Link } from 'react-router-dom';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import { BRAND } from '../content';
import { POLICY_DATE_LABEL } from '../lib/consent';

// Text copied word for word from `Claude outputs/data_collection_policy.md` (approved by Tyler; Brief 26).
// Regenerate from that file rather than editing here.

const UL = 'list-disc space-y-1.5 pl-6 marker:text-slate-600';
const TH = 'border-b border-white/10 py-2 pr-4 font-semibold text-white align-top';
const TD = 'border-b border-white/5 py-2 pr-4 align-top';

const MailLink = () => (
  <a href={`mailto:${BRAND.email}`} className="text-cyan hover:underline">
    {BRAND.email}
  </a>
);

const SECTIONS = [
  {
    heading: '1. What This Policy Covers',
    body: (
      <p>This policy explains what data OVOXI, Inc. ("OVOXI", "we") collects when you visit ovoxi.net, the technologies that collect it, what we do with it, and the choices we give you when you visit. It forms part of our <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link>, which describes your rights and how to use them. If the two differ on a point, the <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link> controls.</p>
    ),
  },
  {
    heading: '2. Data We Collect',
    body: (
      <>
        <p><strong className="text-white">Data you give us.</strong> Account details, artist and song information, ownership splits, buyer orders and projects, messages, and the choices you make in our prompts. The <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link> lists each category in full.</p>
        <p><strong className="text-white">Data collected automatically when you visit:</strong></p>
        <ul className={UL}>
          <li>IP address and approximate location (city, region and country);</li>
          <li>browser, operating system, device type, screen size and language;</li>
          <li>a random identifier stored in a cookie or in your browser's local storage so that we can recognize repeat visits;</li>
          <li>pages viewed, time on each page, links and buttons clicked, and how you reached the site, including referring pages and campaign tags;</li>
          <li>catalog activity: searches, filters, songs previewed and for how long, songs saved or added to a license; and</li>
          <li>session replay of how you scroll, click and move through pages, with typed text masked.</li>
        </ul>
        <p><strong className="text-white">Data from partners.</strong> Stripe tells us about payments and payout verification, Clerk about sign-ins, and ACRCloud about fingerprint matches. Marketing and analytics partners may tell us how you found us.</p>
      </>
    ),
  },
  {
    heading: '3. Technologies We Use',
    body: (
      <>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead><tr><th className={TH}>Category</th><th className={TH}>What it does</th><th className={TH}>Tools</th><th className={TH}>When it runs</th></tr></thead>
            <tbody>
              <tr><td className={TD}>Essential</td><td className={TD}>Signs you in, keeps your session secure, remembers your privacy choices, processes payments, protects against abuse</td><td className={TD}>Clerk, Stripe, our own site storage</td><td className={TD}>Always. The site cannot work without it</td></tr>
              <tr><td className={TD}>Analytics and session replay</td><td className={TD}>Measures how the site and catalog are used, and records sessions so that we can fix problems and improve pages</td><td className={TD}>PostHog</td><td className={TD}>Only after you accept analytics</td></tr>
              <tr><td className={TD}>Advertising and data sharing</td><td className={TD}>Measures our marketing and lets us sell or share data with partners as described in the <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link></td><td className={TD}>Partners we add from time to time, listed on this page when added</td><td className={TD}>Only if you accept, and never after you opt out</td></tr>
            </tbody>
          </table>
        </div>
        <p>We do not run analytics, session replay, advertising or data sharing technologies until you accept them in the prompt. Session replay is turned off on account, signing, payment and OVOXI Wallet pages.</p>
      </>
    ),
  },
  {
    heading: '4. The Data Collection Prompt',
    body: (
      <>
        <p>Until you create an account, we show this prompt at the start of every visit:</p>
        <blockquote className="space-y-2 rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p><strong className="text-white">Your data, your choice</strong></p>
          <p>OVOXI uses essential technologies to run the site. With your permission, we also use analytics and session replay to improve it, and we sell or share some data with music, technology and marketing partners. See our Data Collection Policy and <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link>.</p>
          <p>[Accept all] [Reject] [Customize]</p>
        </blockquote>
        <p><strong className="text-white">Customize</strong> lets you turn each category on or off:</p>
        <ul className={UL}>
          <li>Essential (always on)</li>
          <li>Analytics and session replay</li>
          <li>Advertising and data sharing (selling or sharing personal information)</li>
        </ul>
        <p>Your choice applies for the rest of that visit. If you are in the European Economic Area, the United Kingdom or Switzerland, a choice to reject is remembered on that device for 6 months instead of being asked again each visit.</p>
      </>
    ),
  },
  {
    heading: '5. When You Create an Account',
    body: (
      <>
        <p>When you create an account, the choices from your current visit are saved to your account, with the date, time, the choices made and this policy's "Last updated" date. From then on we apply those choices whenever you are signed in, on any device, and we stop showing the prompt. You can change them at any time in My account, under Privacy choices.</p>
        <p>If we add a new category of data use that needs your agreement, we will ask you again.</p>
      </>
    ),
  },
  {
    heading: '6. Global Privacy Control',
    body: (
      <p>If your browser sends a Global Privacy Control signal, we treat it as a choice to reject advertising and data sharing for that browser, and for your account when you are signed in. We do not switch it back on unless you turn it on yourself.</p>
    ),
  },
  {
    heading: '7. How We Use This Data',
    body: (
      <>
        <p>We use the data described here to:</p>
        <ul className={UL}>
          <li>run and secure the site;</li>
          <li>understand which songs, genres and features people use, and set prices;</li>
          <li>recommend songs and plans and personalize the site;</li>
          <li>measure and improve our marketing;</li>
          <li>build aggregated or de-identified insights, such as catalog demand by genre, mood or use, which we may share or sell; and</li>
          <li>sell or share personal information with partners, where you have not opted out, as the <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link> describes.</li>
        </ul>
      </>
    ),
  },
  {
    heading: '8. Keeping and Deleting This Data',
    body: (
      <p>Analytics and session replay data is kept for the period set in PostHog and then deleted. Records of your privacy choices are kept as the <Link to="/privacy" className="text-cyan hover:underline">Privacy Policy</Link> describes. You can ask us to delete data linked to you by emailing tyler@ovoxi.net.</p>
    ),
  },
  {
    heading: '9. Changes and Contact',
    body: (
      <p>We may update this policy and will change the "Last updated" date when we do. Questions go to tyler@ovoxi.net or OVOXI, Inc., 2389 Main St. Ste 100, Glastonbury, CT, 06033, United States.</p>
    ),
  },
];

const DataPolicyPage = () => (
  <div data-testid="data-policy-page">
    <PageHero
      testid="data-policy-hero"
      label="Legal"
      title="Data Collection Policy"
      subtitle={`Last updated ${POLICY_DATE_LABEL}`}
    />

    <section className="bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-3xl px-6 lg:px-8">
        <div className="space-y-12">
          {SECTIONS.map((s) => (
            <Reveal key={s.heading}>
              <h2 className="font-heading text-xl font-semibold text-white sm:text-2xl">
                {s.heading}
              </h2>
              <div className="mt-4 space-y-4 text-base leading-relaxed text-slate-400">
                {s.body}
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  </div>
);

export default DataPolicyPage;
