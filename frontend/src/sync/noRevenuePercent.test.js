// Brief 25b decision 6: no revenue percentages anywhere on the website. Percentages live
// only in the agreements. Ownership splits ("Writer, 50%") and buyer discounts are not
// revenue shares, so the patterns look for share or earnings wording next to a number.
const fs = require('fs');
const path = require('path');

const FILES = [
  'upload/SongForm.jsx', 'upload/DeclarationsFields.jsx', 'upload/SongSummaryRow.jsx',
  'sync/SyncIntakeFields.jsx', 'sync/TrackSyncPanel.jsx', 'sync/LicenseModal.jsx',
  'sync/QuoteForm.jsx', 'sync/PricingPage.jsx', 'sync/constants.js', 'sync/labels.js',
  'agreement/AgreementModal.jsx', 'pages/CosignPage.jsx', 'pages/UploadPage.jsx', 'pages/VaultPage.jsx',
  'content.js',
];

const PATTERNS = [
  /\b\d{1,3}(\.\d+)?\s?%\s*(of|instead|share|revenue|net|on\s+(ai|sync|every|each))\b/i,
  /\b(earn|earns|get|gets|share|revenue|payout|paid)\b[^.\n<]{0,40}\b\d{1,3}(\.\d+)?\s?%/i,
  /\b\d{1,3}\s?percent\b/i,
];

test.each(FILES)('%s shows no revenue percentage', (rel) => {
  const file = path.join(__dirname, '..', rel);
  if (!fs.existsSync(file)) return;
  const text = fs.readFileSync(file, 'utf8');
  for (const re of PATTERNS) {
    const m = text.match(re);
    expect(m ? m[0] : null).toBeNull();
  }
});
