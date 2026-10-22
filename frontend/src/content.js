// Central content + data source (pitch deck = source of truth)

export const BRAND = {
  name: "OVOXI",
  tagline: "The Curated Music Catalog Built for the AI Economy",
  email: "tyler@ovoxi.net",
  domain: "ovoxi.net",
  logo: "/logo.png",
  pillars: ["Emerging-First", "Fully Licensed", "AI-Ready"],
};

export const NAV_LINKS = [
  { label: "Pricing", to: "/pricing", requiresVisible: true },
  { label: "Contact", to: "/contact" },
];

export const PROCESS = [
  { step: "01", title: "Artist Submits", body: "Emerging artists submit their catalog and sign our rights grant agreement." },
  { step: "02", title: "We Master & Prepare", body: "We handle professional mastering and 5-stem separation so your music is platform-ready." },
  { step: "03", title: "Ownership Checked", body: "Every track is checked against global audio fingerprint databases, and every co-owner you list signs before a song is licensed." },
  { step: "04", title: "Catalog Licensed", body: "When AI platforms or Sync buyers license your music, you receive payments directly to your OVOXI digital wallet (paid monthly)." },
];

export const AI_COPY = {
  headline: "Culturally Fresh. Legally Clean. AI-Ready.",
};

export const ARTIST_COPY = {
  headline: "Your Music Belongs in the AI Economy.",
};

export const ARTIST_BENEFITS = [
  "Professional mastering",
  "5-stem separation delivered to platforms",
  "Chain-of-title documentation and fingerprinting",
  "Licensing revenue every time your music is used",
  "No upfront cost. We only win when you win.",
];

export const INTEREST_OPTIONS = [
  { value: "ai_company", label: "AI Music Company" },
  { value: "enterprise", label: "Enterprise / Licensing Buyer" },
  { value: "artist", label: "Artist" },
  { value: "other", label: "Other" },
];
