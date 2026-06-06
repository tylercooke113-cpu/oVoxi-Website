// Central content + data source (pitch deck = source of truth)

export const BRAND = {
  name: "oVoxi",
  tagline: "The Curated Music Catalog for the AI Generation",
  email: "ovoxi.ai@gmail.com",
  domain: "ovoxi.net",
  pillars: ["Emerging-First", "Fully Licensed", "AI-Ready"],
};

export const NAV_LINKS = [
  { label: "Company", to: "/about" },
  { label: "Artists", to: "/artists" },
  { label: "Licensing", to: "/licensing" },
  { label: "Investors", to: "/investors" },
  { label: "Contact", to: "/contact" },
];

export const STATS = [
  { value: "$6.65B", label: "AI music market today (2025)" },
  { value: "$60B", label: "Projected market size by 2034" },
  { value: "60,000", label: "AI tracks uploaded to Deezer daily" },
  { value: "33%+", label: "New Apple Music uploads are AI-generated" },
];

export const PROBLEMS = [
  {
    title: "Rights Chaos",
    body: "Studios generate thousands of AI audio assets daily with no mechanism to verify consent, rights clearance, or usage licensing before deployment.",
  },
  {
    title: "No Fresh Catalog",
    body: "Every licensed catalog is backward-looking — production libraries and known catalogs. AI generators training on stale content produce music that sounds like yesterday.",
  },
  {
    title: "No Ownership Trail",
    body: "Independent artists lack PRO registration, mastered files, and documented chain-of-title. There is no scalable way to license what cannot be cleared.",
  },
];

export const PROCESS = [
  { step: "01", title: "Artist Submits", body: "Indie artist uploads a track via the artist portal." },
  { step: "02", title: "We Register & Master", body: "PRO registration, in-house mastering, and stem creation." },
  { step: "03", title: "Ownership Verified", body: "In-house chain-of-title documents every split and rights holder." },
  { step: "04", title: "Catalog Licensed", body: "Fully cleared, AI-ready assets delivered to platforms and buyers." },
];

export const WHY = [
  {
    title: "Freshness First",
    body: "Targeting sounds and genres 12–18 months before mainstream recognition — catalog competitors cannot replicate this in hindsight.",
    icon: "Sparkles",
  },
  {
    title: "Ownership Verified",
    body: "In-house chain-of-title verification at ingestion. No ambiguous ownership. No legal risk for buyers.",
    icon: "ShieldCheck",
  },
  {
    title: "Stems Included",
    body: "Stems command 2–3× higher licensing rates. We deliver stems alongside masters as standard. Most catalogs don't.",
    icon: "Layers",
  },
  {
    title: "Artist Royalties",
    body: "Transparent usage-based splits. Artists earn every time their catalog is licensed — creating the acquisition flywheel.",
    icon: "Coins",
  },
  {
    title: "AI Ready",
    body: "Clean metadata, normalized masters, and a clear licensing structure built for AI training and generation pipelines.",
    icon: "Cpu",
  },
];

export const MARKETS = [
  { title: "AI Music Generators", body: "Suno · Udio · MusicGen · ElevenLabs. Premium for cleared stems + metadata.", icon: "Bot" },
  { title: "Enterprise Licensing", body: "Ad agencies, game studios, film & TV requiring legally defensible audio.", icon: "Building2" },
  { title: "Film & TV", body: "Sync + broadcast rights enabled by documented chain-of-title.", icon: "Clapperboard" },
  { title: "Gaming", body: "Genre-diverse, culturally fresh soundtracks cleared for interactive media.", icon: "Gamepad2" },
  { title: "Advertising", body: "High-ACV campaign licensing with zero rights ambiguity.", icon: "Megaphone" },
];

export const COMPETITORS = ["SourceAudio", "Musicbed", "Artlist"];

export const COMPARISON = [
  { feature: "AI-Ready Licensed Catalog", values: [true, true, true, true] },
  { feature: "Emerging / Pre-Recognition Artists", values: [false, false, false, true] },
  { feature: "In-House PRO Registration", values: [false, false, false, true] },
  { feature: "Stems Delivery Standard", values: [false, false, false, true] },
  { feature: "Chain-of-Title Verification at Ingestion", values: [false, false, false, true] },
  { feature: "Usage-Based Artist Royalties", values: [false, false, false, true] },
  { feature: "Genre-Specific Curated Drops", values: [false, false, false, true] },
];

export const AI_BENEFITS = [
  "Cleared rights at the asset level",
  "Verified, documented ownership",
  "Stems included as standard",
  "Fresh, emerging genres",
  "Genre-diverse, culturally relevant catalog",
  "Dramatically reduced legal risk",
];

export const ARTIST_BENEFITS = [
  "PRO registration handled for you (ASCAP, BMI, SESAC)",
  "Broadcast-standard mastering included",
  "Stems support built in from day one",
  "Recurring licensing opportunities",
  "Transparent, usage-based royalty participation",
];

export const BUSINESS_MODEL = [
  {
    tag: "Primary",
    title: "AI Platform Licensing",
    body: "Annual catalog access deals with AI music generators. Flat fee + per-use royalty structure. SourceAudio proves $10M+ in this category already — we bring what they can't: tomorrow's sound.",
  },
  {
    tag: "Expansion",
    title: "Enterprise Sync",
    body: "Ad agencies, game studios, film & TV production. Per-track licensing for commercial use. Clean ownership records enable deals ambiguous catalogs cannot close.",
  },
  {
    tag: "Differentiated",
    title: "Genre Drop Packages",
    body: "Curated quarterly licensing drops by emerging genre. Sells scarcity and cultural edge — a product category competitors cannot copy retroactively.",
  },
];

export const ROADMAP = [
  { quarter: "Q3 2026", title: "Catalog Build Begins", body: "50+ artist onboarding · PRO + mastering pipeline live." },
  { quarter: "Q4 2026", title: "First Licensing Deal", body: "AI platform pilot · genre drop launch · $50K ARR." },
  { quarter: "Q1 2027", title: "Scale Catalog", body: "200+ artists · stems library complete · enterprise outreach." },
  { quarter: "Q2 2027", title: "Seed Round Ready", body: "$500K+ ARR · 3 platform deals · Seed-ready." },
];

export const TRACTION = [
  "A&R pipeline active — emerging artist sourcing underway",
  "Artist services framework built: PRO, mastering, stems, ownership verification",
  "SourceAudio market proof: $10M+ in AI catalog deals already closed",
  "Demand-side validated: AI platforms actively contracting licensed catalogs",
];

export const USE_OF_FUNDS = [
  { pct: "40%", title: "Catalog Acquisition & Artist Services", body: "PRO registration, mastering, stems delivery, artist onboarding." },
  { pct: "30%", title: "Ownership Verification Platform", body: "Build the chain-of-title system that de-risks every licensing deal." },
  { pct: "20%", title: "Go-to-Market & Business Development", body: "First AI platform licensing deal outreach and BD operations." },
  { pct: "10%", title: "Operations & Legal", body: "Entity formation, licensing templates, contract infrastructure." },
];

export const INTEREST_OPTIONS = [
  { value: "ai_company", label: "AI Music Company" },
  { value: "enterprise", label: "Enterprise / Licensing Buyer" },
  { value: "artist", label: "Artist" },
  { value: "investor", label: "Investor" },
  { value: "other", label: "Other" },
];
