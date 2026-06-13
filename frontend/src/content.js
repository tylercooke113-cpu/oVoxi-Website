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
  { label: "Contact", to: "/contact" },
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

export const INTEREST_OPTIONS = [
  { value: "ai_company", label: "AI Music Company" },
  { value: "enterprise", label: "Enterprise / Licensing Buyer" },
  { value: "artist", label: "Artist" },
  { value: "other", label: "Other" },
];
