import React from 'react';
import { Link } from 'react-router-dom';
import { PageHero } from '../components/PageHero';
import { Reveal } from '../components/Reveal';
import { BRAND } from '../content';
import { POLICY_DATE_LABEL } from '../lib/consent';

// Text copied word for word from `Claude outputs/privacy_policy_final.md` (approved by Tyler; Brief 26).
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
    heading: '1. Who We Are',
    body: (
      <>
        <p>OVOXI ("OVOXI", "we", "us" or "our") is OVOXI, Inc., a Delaware corporation, of 2389 Main St. Ste 100, Glastonbury, CT, 06033, United States. We operate ovoxi.net.</p>
        <p>Through the site, artists license their music to us for AI training and for sync, and we license that music to AI companies and to buyers who use it in videos, ads, films, games and other media.</p>
        <p>This policy explains what personal information we collect, why, who we share or sell it to, and the choices you have. It covers:</p>
        <ul className={UL}>
          <li>visitors to our site;</li>
          <li>artists who apply, sign our agreements, upload music and receive payments;</li>
          <li>co-writers, publishers and other rights holders whom an artist lists on a song;</li>
          <li>buyers who create an account, license music or subscribe; and</li>
          <li>anyone who contacts us.</li>
        </ul>
        <p>Our <Link to="/data-policy" className="text-cyan hover:underline">Data Collection Policy</Link> gives more detail on the technologies we use on the site and the choices offered each visit. We are the controller of the personal information described in this policy.</p>
      </>
    ),
  },
  {
    heading: '2. Information We Collect',
    body: (
      <>
        <p><strong className="text-white">Account information.</strong> When you create an account, our sign-in provider collects your name, email address and password, or the details from the Google account you sign in with. We do not see or store your password.</p>
        <p><strong className="text-white">Artist information.</strong> When you apply, sign the Artist Agreement and upload music, we collect:</p>
        <ul className={UL}>
          <li>your artist name, legal name, postal address and country;</li>
          <li>whether you sign as an individual or for a company;</li>
          <li>the audio files you upload, together with track details such as title, genre, mood, vocals, BPM and key;</li>
          <li>your performing rights organization and IPI number;</li>
          <li>your distributor and Content ID status;</li>
          <li>what you tell us about samples and any use of artificial intelligence tools;</li>
          <li>the ownership splits for each song, and your licensing choices for each song;</li>
          <li>your profile photo and biography, if you add them; and</li>
          <li>your OVOXI Wallet records: amounts credited, held and paid, and your statements.</li>
        </ul>
        <p><strong className="text-white">Payout and tax information.</strong> To pay artists and co-owners, our payment provider, Stripe, collects identity and bank details and your tax form. Stripe verifies your identity. We receive your verification status, the last digits of your bank account, your tax classification and the information needed to issue tax forms. We do not store your full bank account number.</p>
        <p><strong className="text-white">Rights holder information.</strong> When an artist lists co-writers, publishers or master owners on a song, the artist gives us each person's or company's legal name, role, ownership share and email address, and may give their performing rights organization and IPI number. When a rights holder signs or declines our Co-owner Consent, we also collect the name they type, their title if they sign for a company, and the record described under "Signature records" below.</p>
        <p><strong className="text-white">Buyer information.</strong> When you license music or subscribe, we collect:</p>
        <ul className={UL}>
          <li>your name and email address;</li>
          <li>your company, if you give one;</li>
          <li>the songs you license and the projects you register them for;</li>
          <li>your plan, orders, downloads and searches; and</li>
          <li>your billing country and address where needed for tax.</li>
        </ul>
        <p>Stripe collects your card or other payment details directly. We do not receive or store your full card number. We receive limited payment information from Stripe, such as the payment status, card brand, last four digits and billing country.</p>
        <p><strong className="text-white">Signature records.</strong> When you sign the Artist Agreement or a Co-owner Consent, or accept our license terms, we keep a record of what you signed: the date and time, your account or the email address the signing link was sent to, your IP address, which document you signed, and a fingerprint of its text. We also keep a PDF copy of each signed agreement.</p>
        <p><strong className="text-white">Privacy choices.</strong> We keep a record of the choices you make in our data collection prompt and on our privacy choices page, with the date and the policy text shown to you. When you create an account, the choices from your current visit are saved to your account.</p>
        <p><strong className="text-white">Messages and requests.</strong> When you use our contact or quote forms or email us, we collect your name, email address, company and what you write to us.</p>
        <p><strong className="text-white">Information collected automatically.</strong> When you use our site we collect technical information such as:</p>
        <ul className={UL}>
          <li>your IP address and approximate location;</li>
          <li>your browser, device type and device identifiers;</li>
          <li>the pages you visit, the songs you play and search for, and the date and time of each visit;</li>
          <li>how you arrived at the site, such as a link or campaign; and</li>
          <li>the actions you take on the site, including through session replay.</li>
        </ul>
        <p>Session replay records how you move through and interact with our pages. We mask what you type into form fields and hide account, signing and payment pages from replay. The <Link to="/data-policy" className="text-cyan hover:underline">Data Collection Policy</Link> lists the tools we use and when they run.</p>
        <p><strong className="text-white">Information from other sources.</strong> To confirm who owns a song and to detect existing claims, we check uploaded audio with ACRCloud's audio fingerprinting service. We may also receive information from performing rights organizations, distributors, other rights holders, and business and marketing partners.</p>
        <p><strong className="text-white">Inferences.</strong> We may create inferences from the information above, such as your musical interests, the kinds of projects you license for, and your likely interest in our plans.</p>
      </>
    ),
  },
  {
    heading: '3. How We Use Information',
    body: (
      <>
        <p>We use personal information to:</p>
        <ul className={UL}>
          <li>create and secure your account;</li>
          <li>review artist applications and process uploads, including mastering, separating songs into stems, analyzing them and checking ownership;</li>
          <li>prepare, sign and keep records of the Artist Agreement, Co-owner Consents and licenses;</li>
          <li>email rights holders whom an artist has listed, to ask for their consent to license the song;</li>
          <li>list cleared music in our catalog with credit to the artist and rights holders;</li>
          <li>license music to buyers and AI companies, and issue license certificates;</li>
          <li>process payments and subscriptions, keep OVOXI Wallets, calculate, report and pay revenue shares, and issue tax forms;</li>
          <li>send emails about your account, uploads, agreements, licenses, payments and subscription;</li>
          <li>send marketing about OVOXI, where the law allows or you agree, which you can unsubscribe from at any time;</li>
          <li>personalize the site, recommend songs and plans, and measure and improve our marketing;</li>
          <li>analyze how the site and catalog are used, set prices, and develop new products;</li>
          <li>create aggregated or de-identified insights, such as demand by genre, mood or use, which we may share or sell to others;</li>
          <li>sell or share personal information as described in section 6, subject to your right to opt out;</li>
          <li>answer your messages and quote requests;</li>
          <li>prevent fraud and abuse, verify identity, enforce our agreements, and keep the site secure; and</li>
          <li>meet our legal, tax and accounting obligations.</li>
        </ul>
      </>
    ),
  },
  {
    heading: '4. Music, Splits and AI Training',
    body: (
      <>
        <p>We use the music an artist uploads only within the rights granted in the signed Artist Agreement and any Co-owner Consents for that song. We license a song for AI training or for sync only when the artist has opted it into that use.</p>
        <p>For songs uploaded from October 20, 2026, we license a song that has more than one rights holder only after every rights holder the artist listed has signed a Co-owner Consent.</p>
        <p>We keep records linking each license to the songs it covers, so that revenue shares can be calculated, paid and audited. We do not use your personal information, beyond the credits attached to your music, to train AI models.</p>
      </>
    ),
  },
  {
    heading: '5. How We Share Information',
    body: (
      <>
        <p><strong className="text-white">Service providers.</strong> We share information with providers who process it for us under contract:</p>
        <ul className={UL}>
          <li>Clerk (sign-in and accounts);</li>
          <li>Stripe (payments, subscriptions, tax, identity verification and payouts);</li>
          <li>Resend (email delivery);</li>
          <li>Cloudflare (file storage);</li>
          <li>MongoDB Atlas (database);</li>
          <li>Railway and Vercel (hosting);</li>
          <li>Modal (audio processing);</li>
          <li>ACRCloud (audio fingerprinting); and</li>
          <li>PostHog (analytics and session replay).</li>
        </ul>
        <p><strong className="text-white">Buyers and AI companies.</strong> We share the music, its metadata and the credits for each song with the buyers and AI companies who license it. Buyers can see the artist credit on their license certificate. Anyone can check whether a license is valid on our verification page, which shows the song, the license type, the term and the licensee's company or initials.</p>
        <p><strong className="text-white">Rights holders on the same song.</strong> The artist who uploads a song sees the names, shares and signing status of the rights holders they listed. A rights holder who receives a signing link sees the song, the uploader's name and their own share.</p>
        <p><strong className="text-white">Business and marketing partners.</strong> We sell or share personal information with partners as described in section 6.</p>
        <p><strong className="text-white">Professional advisers and authorities.</strong> We share information with our accountants, lawyers and auditors. We also share it with authorities when the law requires it, or when needed to protect our rights or the safety of others.</p>
        <p><strong className="text-white">Business transfers.</strong> If we are involved in a merger, financing, acquisition or sale of assets, information may be transferred as part of that deal. It stays subject to this policy.</p>
      </>
    ),
  },
  {
    heading: '6. Selling and Sharing Personal Information',
    body: (
      <>
        <p>We may sell personal information, or share it for cross-context behavioral advertising, as those terms are used in California and Connecticut privacy laws.</p>
        <p><strong className="text-white">What we may sell or share:</strong></p>
        <ul className={UL}>
          <li>identifiers and contact details: name, email address, company and country;</li>
          <li>commercial information: plans, licenses bought, songs licensed and project types;</li>
          <li>internet activity: pages visited, songs played and searched, and how you reached the site; and</li>
          <li>inferences about your interests.</li>
        </ul>
        <p><strong className="text-white">Who receives it:</strong> music industry partners such as record labels, publishers, music libraries and distributors; AI and technology companies; advertising and analytics partners; and marketing and data partners. They may use it for their own marketing, business development and analytics.</p>
        <p><strong className="text-white">What we never sell or share:</strong> passwords; payment card, bank account or tax identification numbers; identity documents; signature records; precise location; uploaded audio outside the licenses described in section 4; information about co-owners who have not opened an OVOXI account; and information about anyone we know to be under 18.</p>
        <p><strong className="text-white">Your right to opt out.</strong> You can opt out at any time on our <Link to="/privacy-choices" className="text-cyan hover:underline">Do Not Sell or Share My Personal Information</Link> page, linked in the footer of every page, or by choosing "Reject" in our data collection prompt. If your browser sends a Global Privacy Control signal, we treat it as a request to opt out for that browser and, when you are signed in, for your account. After you opt out, we stop selling or sharing your personal information, and we tell partners we have sold or shared it to within the past 90 days where the law requires it.</p>
      </>
    ),
  },
  {
    heading: '7. How Long We Keep Information',
    body: (
      <>
        <p>We keep account information while your account is open.</p>
        <p>We keep signed agreements, signature records, licenses, payment and OVOXI Wallet records and the music records tied to them while the agreement or license is in force, and afterward for as long as we need them for legal, tax and accounting purposes or to resolve disputes. Licenses granted to buyers can continue after an artist leaves, so the records behind them are kept for the life of those licenses.</p>
        <p>We keep privacy choice records for as long as your account is open and for 3 years after, so that we can show which choices you made.</p>
        <p>If an application is not accepted, or an upload was never licensed, we will delete the audio when you ask us to, unless we need it for one of those purposes.</p>
        <p>Analytics and session replay data is kept for the period set in PostHog and then deleted.</p>
      </>
    ),
  },
  {
    heading: '8. Your Choices and Rights',
    body: (
      <>
        <p>Depending on where you live, you may have the right to:</p>
        <ul className={UL}>
          <li>know what personal information we hold about you and get a copy of it;</li>
          <li>correct it;</li>
          <li>delete it;</li>
          <li>opt out of its sale or sharing, of targeted advertising and of profiling;</li>
          <li>object to or limit how we use it; and</li>
          <li>withdraw a consent you gave.</li>
        </ul>
        <p>California and Connecticut residents have these rights, and the right not to be treated differently for using them. Residents of the European Economic Area and the United Kingdom have the rights set out in the GDPR, including the right to complain to their local data protection authority.</p>
        <p>To opt out of sale or sharing, use the <Link to="/privacy-choices" className="text-cyan hover:underline">Do Not Sell or Share My Personal Information</Link> page. To make any other request, email <MailLink />. We will verify the request before acting on it, usually by confirming it comes from the email address on your account. You may use an authorized agent where the law allows. If we refuse a request, you may appeal by replying to our decision, and we will answer within the time the law requires.</p>
        <p>Some information cannot be deleted while an agreement or license is in force. This includes signature records, OVOXI Wallet records, and the credits and splits for licensed music. Deleting it would stop us from honoring the license or paying the people owed. We will tell you if this applies to your request.</p>
        <p>You can unsubscribe from marketing email using the link in it. You can change your data collection choices at any time from the Privacy choices link in the footer or, when signed in, in My account.</p>
      </>
    ),
  },
  {
    heading: '9. Legal Bases (EEA and UK)',
    body: (
      <>
        <p>Where the GDPR applies, we rely on these legal bases:</p>
        <ul className={UL}>
          <li><strong className="text-white">Performing a contract with you:</strong> accounts, uploads, agreements, licenses, OVOXI Wallets and payments.</li>
          <li><strong className="text-white">Our legitimate interests:</strong> keeping the site secure, preventing fraud, checking song ownership, contacting rights holders an artist has listed so that we can get their consent, and creating aggregated insights.</li>
          <li><strong className="text-white">Meeting legal obligations:</strong> tax, accounting and identity verification.</li>
          <li><strong className="text-white">Your consent:</strong> analytics, session replay, advertising, and selling or sharing personal information. We ask for it in our data collection prompt, and you can withdraw it at any time.</li>
        </ul>
      </>
    ),
  },
  {
    heading: '10. International Transfers',
    body: (
      <p>We are based in the United States and our providers store and process information in the United States. If you are outside the United States, your information is transferred there. Where the law requires it, we rely on safeguards such as the European Commission's standard contractual clauses.</p>
    ),
  },
  {
    heading: '11. Security',
    body: (
      <p>We protect personal information with measures that include encrypted connections, private file storage, access limited to the people who need it, and signed links that expire. No method of storage or transmission is completely secure, and we cannot guarantee absolute security.</p>
    ),
  },
  {
    heading: '12. Children',
    body: (
      <p>Our services are for people aged 18 and over. We do not knowingly collect personal information from anyone under 18, and we do not sell or share it. If you believe a child has given us personal information, contact us and we will delete it.</p>
    ),
  },
  {
    heading: '13. Changes to This Policy',
    body: (
      <p>We may update this policy. When we make material changes, we will update the "Last updated" date above and notify you by email or on the site. Where the law requires your consent to a change, we will ask for it.</p>
    ),
  },
  {
    heading: '14. Contact Us',
    body: (
      <p>For questions about this policy or your information, email <MailLink /> or write to OVOXI, Inc., 2389 Main St. Ste 100, Glastonbury, CT, 06033, United States.</p>
    ),
  },
];

const PrivacyPage = () => (
  <div data-testid="privacy-page">
    <PageHero
      testid="privacy-hero"
      label="Legal"
      title="Privacy Policy"
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

export default PrivacyPage;
