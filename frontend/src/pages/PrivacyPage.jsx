import React from 'react';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import { BRAND } from '../content';

const LAST_UPDATED = 'August 21, 2026';

const SECTIONS = [
  {
    heading: '1. Who We Are',
    body: (
      <>
        <p>
          {BRAND.name} ("{BRAND.name}", "we", "us", or "our") operates {BRAND.domain} and related
          services that acquire training and licensing rights to artist music catalogs and connect
          those catalogs with AI platforms and enterprise licensees. This Privacy Policy explains
          what information we collect, how we use it, and the choices you have.
        </p>
        <p>
          This policy applies to visitors of our website, artists who submit or upload catalog
          material, and AI companies or enterprise buyers who inquire about licensing.
        </p>
      </>
    ),
  },
  {
    heading: '2. Information We Collect',
    body: (
      <>
        <p>We collect information in the following ways:</p>
        <p>
          <strong className="text-white">Information you provide directly.</strong> This includes
          your name, email address, company, and message content when you submit our contact form;
          identity and payment details (such as name, address, and banking or payout information)
          when you apply to our catalog acquisition program; and the audio files, metadata, and
          chain-of-title documentation you upload when submitting tracks.
        </p>
        <p>
          <strong className="text-white">Information collected automatically.</strong> When you use
          our site we may collect standard technical data such as IP address, browser type, device
          information, pages visited, and timestamps, typically through server logs and analytics
          tooling.
        </p>
        <p>
          <strong className="text-white">Information from third parties.</strong> Where relevant to
          verifying ownership and clearing a catalog for licensing, we may receive information from
          performing rights organizations, distributors, or rights-verification services (for
          example, ACRCloud) to confirm chain of title and detect existing licenses or conflicts.
        </p>
      </>
    ),
  },
  {
    heading: '3. How We Use Information',
    body: (
      <>
        <p>We use the information we collect to:</p>
        <p>
          Evaluate and process artist catalog submissions, including mastering, stem separation,
          and chain-of-title verification; administer rights-grant agreements and calculate and pay
          mechanical royalty or licensing-revenue splits owed to artists; respond to inquiries from
          artists, AI companies, and enterprise licensing buyers; operate, secure, and improve our
          website and internal tools; and comply with legal, tax, and accounting obligations tied to
          licensing and royalty administration.
        </p>
        <p>
          We do not sell personal information to third parties for their own independent marketing
          purposes.
        </p>
      </>
    ),
  },
  {
    heading: '4. Music, Catalog Data, and AI Training Use',
    body: (
      <>
        <p>
          When an artist submits a catalog to {BRAND.name}, the audio recordings, associated
          metadata, and any chain-of-title documentation are used strictly in accordance with the
          terms of that artist's signed rights-grant agreement. Any licensing of a track to an AI
          platform for model training, or to an enterprise buyer for other licensed use, occurs only
          under the scope of rights the artist has granted, and any associated licensing revenue is
          split with the artist as set out in that agreement and in our Terms of Service.
        </p>
        <p>
          We maintain records tying each licensed generation or use back to the underlying track so
          that royalty and revenue-split payouts can be calculated and audited.
        </p>
      </>
    ),
  },
  {
    heading: '5. Sharing of Information',
    body: (
      <>
        <p>We may share information with:</p>
        <p>
          Service providers who help us operate the business, such as hosting, payment processing,
          email delivery, and audio-fingerprinting or rights-verification vendors, under obligations
          to protect that data; AI platforms and enterprise licensees, limited to what is necessary
          to license and attribute use of a specific track under an active agreement; professional
          advisors such as our accountants and legal counsel; and regulators or authorities where
          required by law, or in connection with a merger, financing, or sale of the business.
        </p>
      </>
    ),
  },
  {
    heading: '6. Data Retention',
    body: (
      <>
        <p>
          We retain personal information and catalog records for as long as needed to administer
          active rights-grant agreements and pay royalties, and thereafter as required to satisfy
          legal, tax, and accounting obligations or to resolve disputes. Where an artist's
          application is not accepted into the catalog, we retain submitted materials only as long
          as necessary to process that decision, unless the artist asks us to delete it sooner.
        </p>
      </>
    ),
  },
  {
    heading: '7. Your Choices and Rights',
    body: (
      <>
        <p>
          Depending on where you live, you may have rights to access, correct, delete, or receive a
          copy of the personal information we hold about you, and to object to or restrict certain
          processing. You can exercise these rights, or ask any question about this policy, by
          emailing{' '}
          <a href={`mailto:${BRAND.email}`} className="text-cyan hover:underline">
            {BRAND.email}
          </a>
          . Because catalog and royalty records are also part of a binding rights-grant agreement,
          some information cannot be deleted while that agreement remains active without affecting
          our ability to pay you correctly.
        </p>
      </>
    ),
  },
  {
    heading: '8. Security',
    body: (
      <p>
        We use reasonable administrative, technical, and organizational safeguards designed to
        protect the information we hold. No method of transmission or storage is completely secure,
        and we cannot guarantee absolute security.
      </p>
    ),
  },
  {
    heading: '9. Children',
    body: (
      <p>
        Our services are not directed to children under 16, and we do not knowingly collect
        personal information from them. If you believe a child has provided us with personal
        information, please contact us so we can address it.
      </p>
    ),
  },
  {
    heading: '10. Changes to This Policy',
    body: (
      <p>
        We may update this Privacy Policy from time to time. If we make material changes, we will
        update the "Last updated" date below and, where appropriate, provide additional notice.
      </p>
    ),
  },
  {
    heading: '11. Contact Us',
    body: (
      <p>
        Questions about this Privacy Policy can be sent to{' '}
        <a href={`mailto:${BRAND.email}`} className="text-cyan hover:underline">
          {BRAND.email}
        </a>
        .
      </p>
    ),
  },
];

const PrivacyPage = () => (
  <div data-testid="privacy-page">
    <PageHero
      testid="privacy-hero"
      label="Legal"
      title="Privacy Policy"
      subtitle={`Last updated ${LAST_UPDATED}`}
    />

    <section className="bg-ink py-20 lg:py-28">
      <div className="mx-auto max-w-3xl px-6 lg:px-8">
        <Reveal>
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 text-sm leading-relaxed text-slate-400 md:p-8">
            This page is a general-purpose Privacy Policy template for {BRAND.name} and has not yet
            been reviewed by legal counsel. Please have an attorney familiar with music rights,
            data privacy, and AI training-data regulation review it before this page is relied on
            for compliance purposes.
          </div>
        </Reveal>

        <div className="mt-12 space-y-12">
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

export default PrivacyPage;
