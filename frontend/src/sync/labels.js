// Plain-language text for clearance reason codes (backend/clearance.py).

const SIMPLE = {
  splits_missing: 'Add your splits',
  splits_writers: "Writer splits don't add up to 100%",
  splits_publishers: "Publisher splits don't add up to 100%",
  splits_master_owners: "Master splits don't add up to 100%",
  splits_not_attested: 'Confirm your splits',
  fingerprint_needs_docs: 'Ownership check needs documents',
  fingerprint_scan_error: "Ownership check couldn't run",
  samples: 'Confirm your samples answer',
  content_id: 'Registered in YouTube Content ID (not eligible for sync)',
  pro: 'Add your PRO and IPI, or mark not affiliated',
  not_scanned: 'Still processing',
};

const FIELD = { bpm: 'BPM', key: 'key', moods: 'moods', vocals: 'vocals', genre: 'genre',
  duration_s: 'duration', stems: 'stems' };

export const reasonText = (code) => {
  if (!code) return null;
  if (SIMPLE[code]) return SIMPLE[code];
  // e.g. "missing: bpm, key; confirm: key"
  return code.split('; ').map((part) => {
    const [kind, list] = part.split(': ');
    const items = (list || '').split(', ').map((f) => FIELD[f] || f).join(', ');
    if (kind === 'missing') return `Missing: ${items}`;
    if (kind === 'confirm') return `Confirm the ${items}`;
    return part;
  }).join('. ');
};
