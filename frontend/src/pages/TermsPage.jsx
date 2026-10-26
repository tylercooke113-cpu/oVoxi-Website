import React from 'react';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import { BRAND } from '../content';

const LAST_UPDATED = 'October 23, 2026';

const Mail = () => (
  <a href={`mailto:${BRAND.email}`} className="text-cyan hover:underline">{BRAND.email}</a>
);

const SECTIONS = [
  {
    heading: '1. Who We Are and Accepting These Terms',
    body: (
      <>
        <p>
          These Terms of Service ("Terms") are an agreement between you and OVOXI, Inc., a Delaware
          corporation, of 2389 Main St. Ste 100, Glastonbury, CT, 06033, United States ("OVOXI", "we", "us" or "our"). They
          govern your use of {BRAND.domain} and every related service we operate (the "Platform").
        </p>
        <p>
          By visiting the Platform, creating an account, uploading music, signing an agreement or
          buying a license, you accept these Terms. If you do not accept them, do not use the Platform.
        </p>
      </>
    ),
  },
  {
    heading: '2. How These Terms Fit With Our Other Agreements',
    body: (
      <>
        <p>Depending on how you use the Platform, other agreements also apply to you:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>the AI Training and Sync Licensing Agreement ("Artist Agreement"), for artists who upload music;</li>
          <li>the Co-owner Consent and License, for writers, publishers and master owners an artist lists on a song;</li>
          <li>the OVOXI Music License Terms, for buyers of sync licenses and subscriptions;</li>
          <li>the OVOXI AI Training License Terms, for buyers of AI training licenses; and</li>
          <li>our Privacy Policy and Data Collection Policy, for everyone.</li>
        </ul>
        <p>
          Where one of those agreements covers a matter, it controls over these Terms for that matter.
          Otherwise these Terms apply.
        </p>
      </>
    ),
  },
  {
    heading: '3. Eligibility and Accounts',
    body: (
      <>
        <p>
          You must be at least 18 years old and have reached the age of majority where you live to
          create an account. If you act for a company, you confirm that you are authorized to bind it.
        </p>
        <p>
          You agree to give accurate information, keep it up to date, keep your sign-in details secure,
          and tell us right away at <Mail /> if you suspect someone else is using your account. You are
          responsible for activity on your account. One account is for one person or one company.
        </p>
      </>
    ),
  },
  {
    heading: '4. The Platform',
    body: (
      <>
        <p>Through the Platform:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>artists upload music, sign the Artist Agreement, choose for each song whether to license it for AI training, for sync, or both, and whether it is offered to many buyers or sold once, as an exclusive license;</li>
          <li>OVOXI prepares the music for licensing, including mastering, separating it into stems, analyzing it, and checking it against audio fingerprint databases;</li>
          <li>songs that pass our checks are listed in the OVOXI Catalog, which anyone may browse and preview; and</li>
          <li>buyers create an account to license songs for sync or for AI training, at the prices and on the terms shown at checkout, or by quote for exclusive songs.</li>
        </ul>
        <p>
          Prices, plans and features are shown on the Platform and may change. A change does not affect
          a license or subscription period already paid for.
        </p>
      </>
    ),
  },
  {
    heading: '5. Artists',
    body: (
      <>
        <p>
          You may upload music only after we approve your account and you sign the Artist Agreement.
          You keep ownership of your music. The rights you grant OVOXI, the payments you receive and
          the way songs are withdrawn are set out in the Artist Agreement and the choices you record on
          the Platform.
        </p>
        <p>
          A song may be offered for sync only if every writer is affiliated with a performing rights
          organization and their details are entered on the Platform. Songs without that information
          may be offered for AI training only.
        </p>
        <p>
          Songs may not contain samples of other recordings or compositions. A song that uses a
          royalty-free loop may be offered for sync only, after each loop creator is listed on the song
          and gives their consent, and after we approve the loop's license. Songs with loops can't be
          offered for AI training.
        </p>
        <p>
          When you upload a song, you confirm that every statement you make about it is true, including
          its ownership splits, its co-owners, its samples, any part made with artificial intelligence
          tools, its performing rights organization details and its Content ID status. We may refuse,
          remove or stop licensing any song at our discretion, including when a check is not passed or a
          claim is made.
        </p>
      </>
    ),
  },
  {
    heading: '6. OVOXI Wallet and Payments to Artists and Co-owners',
    body: (
      <>
        <p>
          Every artist, and every co-owner who signs a Co-owner Consent, has an OVOXI Wallet. It shows
          the amounts credited to you from licenses and subscriptions, any amounts deducted or held,
          your statements, and your payments.
        </p>
        <p>
          Payments are made monthly, as set out in the Artist Agreement, by transfer to the bank account
          you connect through our payment provider, Stripe. Before your first payment you must complete
          Stripe's identity and account verification and provide a tax form. Amounts accrue in your OVOXI
          Wallet until you do.
        </p>
        <p>
          Your OVOXI Wallet is a record of amounts credited to you under the applicable agreements and does
          not itself create or modify any payment obligation. It is not a bank or deposit account, does not
          earn interest, and its balance cannot be spent, transferred or withdrawn on the Platform except
          through the scheduled payments. We may hold amounts tied to a claim, a refund, a chargeback or
          suspected fraud, and we may correct errors, including by deducting an overpayment from later
          amounts.
        </p>
      </>
    ),
  },
  {
    heading: '7. Buyers',
    body: (
      <>
        <p>
          A license is granted when checkout is complete and payment is received, under the license
          terms shown at checkout. Subscriptions renew automatically until cancelled. Taxes are added at
          checkout where required. Refunds, chargebacks, download limits and permitted uses are governed
          by the applicable license terms.
        </p>
        <p>
          You may browse and preview the OVOXI Catalog without an account. Previews are for evaluating
          songs only and grant no license.
        </p>
      </>
    ),
  },
  {
    heading: '8. Acceptable Use',
    body: (
      <>
        <p>You agree not to:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>upload music or information you do not have the right to provide, or list a co-owner whose details are false;</li>
          <li>download, record, capture or copy previews, or download songs in bulk or by automated means;</li>
          <li>use the Platform or any audio, stem, metadata or other content from it to train, test or improve any artificial intelligence or machine-learning model, except under an AI training license bought from OVOXI;</li>
          <li>scrape, crawl or index the Platform by automated means, except search engines that follow our robots instructions;</li>
          <li>get around, disable or test any security feature, rate limit or download limit;</li>
          <li>copy, reverse engineer or resell any part of the Platform;</li>
          <li>send spam, harass anyone, or use the co-owner invitation feature for anything other than inviting genuine co-owners; or</li>
          <li>use the Platform in any unlawful way.</li>
        </ul>
      </>
    ),
  },
  {
    heading: '9. Copyright Complaints',
    body: (
      <>
        <p>
          We respect copyright and respond to notices that meet the requirements of the Digital
          Millennium Copyright Act. If you believe material on the Platform infringes your copyright,
          send a notice to our designated agent:
        </p>
        <p>OVOXI, Inc., Attn: Copyright Agent, 2389 Main St. Ste 100, Glastonbury, CT, 06033, United States, <Mail /></p>
        <p>
          Your notice must include: your physical or electronic signature; identification of the
          copyrighted work; identification of the material you say infringes it and where it appears on
          the Platform; your contact details; a statement that you believe in good faith the use is not
          authorized by the owner, its agent or the law; and a statement, under penalty of perjury, that
          the notice is accurate and that you are the owner or authorized to act for the owner.
        </p>
        <p>
          If material you provided is removed and you believe that was a mistake, you may send a
          counter-notice to the same address with the information the law requires. We will end the
          accounts of users who repeatedly infringe.
        </p>
      </>
    ),
  },
  {
    heading: '10. Our Rights in the Platform',
    body: (
      <>
        <p>
          The OVOXI name and logo, and the Platform's design, software and content, other than music and
          materials supplied by artists and co-owners, belong to OVOXI or its licensors. You may not use
          them without our written permission.
        </p>
        <p>If you send us ideas or feedback, we may use them without any obligation to you.</p>
      </>
    ),
  },
  {
    heading: '11. Third-Party Services',
    body: (
      <p>
        The Platform relies on providers including Clerk for sign-in and Stripe for payments,
        subscriptions, tax and payouts. Your use of those features is also subject to their terms. We
        are not responsible for services we do not control.
      </p>
    ),
  },
  {
    heading: '12. Suspension and Termination',
    body: (
      <>
        <p>
          We may suspend or close your account, remove content or stop providing any part of the
          Platform if you breach these Terms or any other agreement with us, if required by law, or to
          protect artists, buyers or OVOXI. You may close your account at any time by emailing <Mail />.
        </p>
        <p>
          Closing an account does not end licenses already granted, amounts already owed, or any part of
          these Terms or another agreement that by its nature continues.
        </p>
      </>
    ),
  },
  {
    heading: '13. Disclaimers',
    body: (
      <p>
        Except as expressly stated in a signed agreement or in license terms you accept, the Platform
        and its content are provided "as is" and "as available", without warranties of any kind, express
        or implied, including warranties of merchantability, fitness for a particular purpose and
        non-infringement, to the fullest extent permitted by law. We do not promise that the Platform
        will be uninterrupted or error free, or that any song will be accepted, listed or licensed, or
        earn any amount.
      </p>
    ),
  },
  {
    heading: '14. Limitation of Liability',
    body: (
      <p>
        To the fullest extent permitted by law, OVOXI is not liable for any indirect, incidental,
        special, consequential or punitive damages, or for lost profits, revenue or data, arising out of
        or related to the Platform. Except as a signed agreement or license terms you accept provide
        otherwise, OVOXI's total liability to you for all claims related to the Platform is limited to
        the greater of the amounts you paid OVOXI in the 12 months before the claim arose and one hundred
        US dollars ($100).
      </p>
    ),
  },
  {
    heading: '15. Indemnity',
    body: (
      <p>
        You agree to defend, indemnify and hold harmless OVOXI and its officers, employees and agents
        against third-party claims, and related losses, costs and reasonable legal fees, arising from
        material or information you provide, your use of the Platform, or your breach of these Terms.
      </p>
    ),
  },
  {
    heading: '16. Disputes',
    body: (
      <>
        <p>
          These Terms are governed by the laws of the State of Connecticut and, where applicable, the
          federal laws of the United States, without regard to conflict-of-laws principles.
        </p>
        <p>
          A dispute under the Artist Agreement, a Co-owner Consent or license terms is resolved as that
          agreement provides. Any other dispute is resolved by binding arbitration administered by the
          American Arbitration Association under its applicable rules, before a single arbitrator seated
          in New Haven County, Connecticut, which may be conducted remotely. Disputes are resolved only
          on an individual basis, not as a class, collective or representative action. Either party may
          bring an individual claim in small claims court, and either party may seek injunctive relief in
          any court of competent jurisdiction to protect its intellectual property.
        </p>
      </>
    ),
  },
  {
    heading: '17. Changes to These Terms',
    body: (
      <p>
        We may update these Terms. We will post the update with a new "Last updated" date and, for
        material changes, tell account holders by email or on the Platform. An update applies from the
        date it is posted. Continuing to use the Platform after that date means you accept it. A signed
        agreement changes only as that agreement allows.
      </p>
    ),
  },
  {
    heading: '18. General',
    body: (
      <p>
        You may not transfer your rights under these Terms without our written consent. We may assign
        them to an affiliate or a successor. If any part of these Terms is unenforceable, the rest remains
        in effect. Our failure to enforce a part is not a waiver. Notices to you may be sent to the email
        address on your account. Notices to us go to <Mail />.
      </p>
    ),
  },
  {
    heading: '19. Contact',
    body: (
      <p>OVOXI, Inc., 2389 Main St. Ste 100, Glastonbury, CT, 06033, United States, <Mail /></p>
    ),
  },
];

const TermsPage = () => (
  <div data-testid="terms-page">
    <PageHero
      testid="terms-hero"
      label="Legal"
      title="Terms of Service"
      subtitle={`Last updated ${LAST_UPDATED}`}
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

export default TermsPage;
