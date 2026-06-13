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
  { label: "Contact", to: "/contact" },
];

export const PROCESS = [
  { step: "01", title: "Artist Submits", body: "Indie artist uploads a track via the artist portal." },
  { step: "02", title: "We Register & Master", body: "PRO registration, in-house mastering, and stem creation." },
  { step: "03", title: "Ownership Verified", body: "In-house chain-of-title documents every split and rights holder." },
  { step: "04", title: "Catalog Licensed", body: "Fully cleared, AI-ready assets delivered to platforms and buyers." },
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
