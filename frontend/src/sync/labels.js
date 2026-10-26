// Plain-language text for clearance reason codes (backend/clearance.py).

const SIMPLE = {
  splits_missing: 'Add your splits',
  splits_writers: "Writer splits don't add up to 100%",
  splits_publishers: "Publisher splits don't add up to 100%",
  splits_master_owners: "Master splits don't add up to 100%",
  splits_not_attested: 'Confirm your splits',
  fingerprint_needs_docs: 'Ownership check needs documents',
  fingerprint_scan_error: "Ownership check couldn't run",
  samples: 'Answer the samples question',
  samples_not_allowed: "Songs that sample other recordings can't be listed",
  samples_loop_ai: "Songs with loops can't be offered for AI training",
  loops_missing: 'List the loops you used',
  loop_creator_not_listed: 'Add each loop creator to the splits with the same email',
  loop_license_missing: 'Upload a license for each loop',
  loop_license_review: 'OVOXI is reviewing your loop licenses',
  loop_license_rejected: 'A loop license was not accepted. Contact us.',
  ai_tools: 'Answer the AI tools question',
  ai_tools_review: 'OVOXI is reviewing the AI-generated parts',
  ai_tools_rejected: 'Not accepted because of AI-generated parts. Contact us.',
  ai_tools_full: "Songs made mostly with AI can't be listed",
  content_id: 'Registered in YouTube Content ID (not eligible for sync)',
  pro: 'Sync needs your PRO and IPI',
  pro_writers: "Sync needs every writer's PRO and IPI",
  cosign_pending: 'Waiting for co-owners to sign',
  cosign_declined: 'A co-owner declined to sign',
  not_scanned: 'Still processing',
};

// Reasons that clear on their own or on OVOXI's side: the song shows "Pending checks".
export const PENDING_REASONS = ['ai_tools_review', 'loop_license_review', 'cosign_pending', 'not_scanned'];

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
