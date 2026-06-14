// Central content + data source (pitch deck = source of truth)

export const BRAND = {
  name: "oVoxi",
  tagline: "The Curated Music Catalog Built for the AI Economy",
  email: "ovoxi.ai@gmail.com",
  domain: "ovoxi.net",
  logo: "/logo.png",
  pillars: ["Emerging-First", "Fully Licensed", "AI-Ready"],
};

export const NAV_LINKS = [
  { label: "Company", to: "/about" },
  { label: "Artists", to: "/artists" },
  { label: "Contact", to: "/contact" },
];

export const PROCESS = [
  { step: "01", title: "Artist Submits", body: "Emerging artists under 50K monthly listeners submit their catalog and sign our rights grant agreement." },
  { step: "02", title: "We Register & Master", body: "We handle PRO registration, professional mastering, and 4-stem separation so your music is platform-ready." },
  { step: "03", title: "Ownership Verified", body: "Chain-of-title documentation and acoustic fingerprinting confirm every track is fully cleared." },
  { step: "04", title: "Catalog Licensed", body: "AI platforms and enterprise clients license your music. You get paid." },
];

export const AI_COPY = {
  headline: "Culturally Fresh. Legally Clean. AI-Ready.",
  body: "Stop building on gray-area catalog. oVoxi delivers emerging artist recordings with stems, metadata, and chain-of-title documentation that enterprise deals require.",
};

export const ARTIST_COPY = {
  headline: "Your Music Belongs in the AI Economy.",
  body: "We handle everything — registration, mastering, stems, clearance. You focus on creating. We get your catalog licensed.",
};

export const ARTIST_BENEFITS = [
  "PRO Registration handled for you",
  "Professional mastering via LANDR",
  "4-stem separation delivered to platforms",
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
