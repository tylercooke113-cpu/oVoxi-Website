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

export const IPI_PATTERN = /^\d{9,11}$/;
