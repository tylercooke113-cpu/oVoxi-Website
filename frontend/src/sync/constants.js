// Fixed vocabularies. Must stay in step with backend/sync_constants.py.

export const MOODS = [
  'Uplifting', 'Happy', 'Hopeful', 'Confident', 'Energetic',
  'Aggressive', 'Epic', 'Luxurious', 'Gritty', 'Chill',
  'Dreamy', 'Romantic', 'Sensual', 'Nostalgic', 'Sentimental',
  'Sad', 'Dark', 'Tense', 'Mysterious', 'Playful',
];
export const MAX_MOODS = 3;

export const VOCALS_OPTIONS = [
  { value: 'vocal', label: 'Vocal' },
  { value: 'instrumental', label: 'Instrumental' },
];

export const SAMPLE_OPTIONS = [
  { value: 'original', label: 'Fully original, no samples or loops' },
  { value: 'cleared_sample', label: 'Contains a sample I have cleared' },
  { value: 'royalty_free_loop', label: 'Uses a royalty-free loop whose license allows sync' },
];

export const CONTENT_ID_OPTIONS = [
  { value: 'no', label: 'No' },
  { value: 'yes', label: 'Yes' },
  { value: 'not_sure', label: 'Not sure' },
];

export const DISTRIBUTORS = [
  'DistroKid', 'TuneCore', 'CD Baby', 'UnitedMasters', 'Amuse',
  'Symphonic', 'Other', 'Not released yet',
];

export const PRO_ORGS = [
  'ASCAP', 'BMI', 'SESAC', 'GMR', 'SOCAN', 'PRS for Music',
  'APRA AMCOS', 'SACEM', 'GEMA', 'SAMRO', 'COSON', 'Other',
];

// IPI name numbers: 11 digits, or 9 for older CAE numbers (PRD-03 decision 8).
export const IPI_PATTERN = /^(\d{9}|\d{11})$/;

// Rights (splits). See docs/PRD-02 section 3.
export const MAX_PARTIES = 4;
export const TOTAL_BP = 10000; // basis points, 100.00%

export const WRITER_ROLES = [
  { value: 'CA', label: 'Composer & lyricist' },
  { value: 'C', label: 'Composer' },
  { value: 'A', label: 'Lyricist' },
  { value: 'AR', label: 'Arranger' },
  { value: 'AD', label: 'Adaptor' },
  { value: 'TR', label: 'Translator' },
];

export const PUBLISHER_ROLES = [
  { value: 'E', label: 'Original publisher' },
  { value: 'AM', label: 'Administrator' },
  { value: 'SE', label: 'Sub-publisher' },
  { value: 'PA', label: 'Income participant' },
];

// BPM and key at upload (PRD-03 4.4). Must match backend/sync_constants.py.
export const BPM_MIN = 20;
export const BPM_MAX = 300;
const PITCHES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
export const MAJOR_KEYS = PITCHES.map((p) => `${p} major`);
export const MINOR_KEYS = PITCHES.map((p) => `${p} minor`);

// Broadcast single-country territories (Brief 18). Must stay in step with backend/sync_constants.py.
export const COUNTRIES = [
  ['US', 'United States'], ['CA', 'Canada'], ['GB', 'United Kingdom'], ['AU', 'Australia'], ['DE', 'Germany'],
  ['FR', 'France'], ['IE', 'Ireland'], ['NL', 'Netherlands'], ['ES', 'Spain'], ['IT', 'Italy'], ['SE', 'Sweden'],
  ['NO', 'Norway'], ['DK', 'Denmark'], ['FI', 'Finland'], ['BE', 'Belgium'], ['AT', 'Austria'], ['CH', 'Switzerland'],
  ['PT', 'Portugal'], ['PL', 'Poland'], ['NZ', 'New Zealand'], ['JP', 'Japan'], ['KR', 'South Korea'],
  ['SG', 'Singapore'], ['BR', 'Brazil'], ['MX', 'Mexico'], ['AR', 'Argentina'], ['ZA', 'South Africa'],
  ['IN', 'India'], ['AE', 'United Arab Emirates'], ['HK', 'Hong Kong'],
].map(([code, name]) => ({ code, name }));

// Subscriptions (Brief 19). After returning from Stripe Checkout, poll /me until the plan mirrors.
export const SUB_POLL_INTERVAL_MS = 2000;
export const SUB_POLL_TIMEOUT_MS = 20000;
export const SUB_POLLING_COPY = 'Confirming your plan. This takes a few seconds.';
export const SUB_POLL_TIMEOUT_COPY = 'This is taking longer than usual. Refresh the page in a minute.';

// Thousands separators for download counts and caps ("1,000").
const nf = (n) => Number(n).toLocaleString('en-US');

// Subscription status chips. Source: subscriptions-mockup.html (approved 2026-10-06).
export const SUB_STATUS_LABELS = {
  active: 'Active',
  past_due: 'Payment failed',
  ending: (date) => `Ends ${date}`,
};

// Subscription UI copy, word for word from the approved mockups (subscriptions-mockup.html,
// and the subscribe pop-up in pricing-licensing-mockup.html). Brief 19 items 10-12. Where the
// brief and a mockup disagreed, the mockup wins (Tyler 2026-10-08). Plan labels/prices/caps are
// NOT here; the client reads them from GET /api/sync/checkout/config. Functions interpolate
// already-formatted values (plan name, counts, dates, money strings); no math lives here.
export const SUB_COPY = {
  // LicenseModal (mockup screens 1 and 5)
  signedOutHint: 'Have a subscription? Sign in to use this track with your plan.',
  planBanner: (plan, left, cap) => `${plan} plan · ${nf(left)} of ${nf(cap)} downloads left this month · 50 a day`,
  choicePlan: (plan) => `Use with my ${plan} plan`,
  choicePlanSub: 'Included. Counts as 1 download.',
  choiceSingle: 'Buy a single license',
  choiceSingleSub: "For uses your plan doesn't cover.",
  includeStems: 'Include stems and instrumental',
  publishAck: "I'll publish this project within 6 months, under the oVoxi Music License Terms.",
  registerButton: 'Register project and download',
  registerFootnote: (left) => `No charge. Uses 1 of your ${nf(left)} remaining downloads.`,
  doneTitle: 'Project registered',
  doneBody: (project, plan) => `${project} is licensed under your ${plan} plan.`,
  doneLicenseLine: (licenseId) => `License ID ${licenseId} · it stays licensed even if you cancel later.`,
  certificateButton: 'Certificate (PDF)',
  downloadButton: 'Download files',
  registerBusy: 'Registering',
  registerPublishError: 'Confirm you will publish within 6 months to continue.',
  registerError: 'Could not register the project. Try again.',
  certificateError: 'Could not open the certificate. Try again.',
  // LicenseModal blocked-state banners (brief item 10.5). Monthly cap carries the "{Plan} plan ·"
  // banner prefix the mockup shows; the others are bare sentences.
  blockedMonthCap: (plan, cap, resetDate) => `${plan} plan · You've used all ${nf(cap)} downloads this month. Your limit resets on ${resetDate}. You can still buy a single license.`,
  blockedDayCap: "You've reached 50 downloads today. Try again tomorrow, or buy a single license.",
  blockedPayment: 'Your last payment failed. Update your card in My account to keep downloading.',
  blockedDispute: 'Downloads are paused while a payment dispute is open.',
  // SubscriptionTab (mockup screens 2 to 4)
  planHeading: (plan, intervalWord) => `${plan} plan, ${intervalWord}`,
  memberSince: (date) => `Member since ${date}`,
  fieldCurrentPrice: 'Current price',
  fieldNextPayment: 'Next payment',
  fieldDownloadsThisMonth: 'Downloads this month',
  fieldRegisteredProjects: 'Registered projects',
  fieldAmountDue: 'Amount due',
  fieldDownloads: 'Downloads',
  downloadsAvailableUntil: (date) => `Available until ${date}`,
  loyaltyPct: (pct) => `(${pct}% loyalty)`,
  loyaltyLabel: 'Loyalty pricing:',
  loyaltyBefore20: (price, nth, date) => `you'll pay ${price} from your ${nth} month (${date}).`,
  loyaltyAt20: "You're on the best monthly price.",
  loyaltyTail: (fullPrice) => `Switching plans keeps your discount. If you cancel and come back, pricing starts again at ${fullPrice}.`,
  loyaltyAnnualTab: "Annual plans don't get loyalty pricing.",
  graceWarning: (date) => `Your last payment didn't go through. Update your card by ${date} to keep downloading. Projects you already registered stay licensed.`,
  graceButton: 'Update payment method',
  endingInfo: (date) => `Your plan is cancelled and ends on ${date}. You can keep registering projects until then. Every project you registered stays licensed after it ends.`,
  endingNote: (date) => `If you restart before ${date}, your loyalty pricing continues. After that, a new subscription starts at the standard price.`,
  endingButton: 'Keep my plan',
  manageBilling: 'Manage billing',
  viewProjects: 'View my projects',
  noPlan: "You don't have a plan yet.",
  noPlanButton: 'Choose a plan',
  planEnded: 'Your plan has ended. Projects you registered stay licensed.',
  // SubscribeModal (subscribe pop-up in pricing-licensing-mockup.html, approved 2026-10-02).
  // subscribeLoyaltyMonthly receives m/p15/p7 pre-formatted from the server; no discount math here.
  subscribeTitle: (plan) => `Subscribe to ${plan}`,
  subscribeSubtitle: 'Create an account or sign in to continue.',
  billingMonthly: 'Monthly',
  billingAnnual: 'Annual',
  priceMonth: (m) => `${m}/month`,
  priceYear: (y) => `${y}/year, 2 months free`,
  subscribeLoyaltyMonthly: (m, p15, p7) => `Loyalty pricing: ${m} for months 1 and 2, ${p15} from month 3, ${p7} from month 7. Switching plans keeps your discount. If you cancel and resubscribe, pricing returns to ${m}. No free trial.`,
  subscribeLoyaltyAnnual: (y) => `Annual plan: billed ${y} once a year. Loyalty discounts apply to monthly plans only. Full refund within 14 days if you have not registered a project. No free trial.`,
  subscribeBullets: [
    'Renews automatically. Cancel any time; access continues to the end of the paid period.',
    'Projects you register while subscribed stay licensed after you cancel.',
    'Tax is added at checkout where applicable.',
  ],
  subscribeDownloadsBullet: (cap) => `Up to ${nf(cap)} downloads a month, 50 a day.`,
  subscribeAgree: 'I agree to the oVoxi Music License Terms, including automatic renewal.',
  subscribeTotal: (price) => `Today ${price}`,
  taxSuffix: '+ tax',
  subscribeButton: 'Continue to secure payment',
};
