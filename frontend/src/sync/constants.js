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
