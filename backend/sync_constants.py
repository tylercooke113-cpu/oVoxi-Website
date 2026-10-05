"""Fixed vocabularies for sync marketplace fields. See docs/PRD-03.

Must stay in step with frontend/src/sync/constants.js.
"""

MOODS = (
    "Uplifting", "Happy", "Hopeful", "Confident", "Energetic",
    "Aggressive", "Epic", "Luxurious", "Gritty", "Chill",
    "Dreamy", "Romantic", "Sensual", "Nostalgic", "Sentimental",
    "Sad", "Dark", "Tense", "Mysterious", "Playful",
)
MAX_MOODS = 3

VOCALS = ("vocal", "instrumental")

SAMPLE_DECLARATIONS = ("original", "cleared_sample", "royalty_free_loop")

CONTENT_ID_ANSWERS = ("yes", "no", "not_sure")

DISTRIBUTORS = (
    "DistroKid", "TuneCore", "CD Baby", "UnitedMasters", "Amuse",
    "Symphonic", "Other", "Not released yet",
)

PRO_ORGS = (
    "ASCAP", "BMI", "SESAC", "GMR", "SOCAN", "PRS for Music",
    "APRA AMCOS", "SACEM", "GEMA", "SAMRO", "COSON", "Other",
)

# IPI name numbers: 11 digits, or 9 for older CAE numbers (PRD-03 decision 8).
IPI_PATTERN = r"^(\d{9}|\d{11})$"

# Rights (splits). See docs/PRD-02 section 3.
MAX_PARTIES = 4
TOTAL_BP = 10000  # basis points, 100.00%
WRITER_ROLES = ("CA", "C", "A", "AR", "AD", "TR")
PUBLISHER_ROLES = ("E", "AM", "SE", "PA")

# Detected metadata (PRD-03 4.4). Must match infra/modal/audio_analysis.py.
PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MUSICAL_KEYS = tuple(f"{p} {m}" for m in ("major", "minor") for p in PITCHES)
BPM_MIN, BPM_MAX = 20, 300

# Upload genres. Must match VALID_GENRES in server.py (test_sync_search checks).
GENRES = (
    "Hip-Hop", "R&B", "Afrobeats", "Trap", "Soul", "Pop",
    "Electronic", "Latin", "Reggaeton", "Afropop", "Other",
)

# Broadcast single-country territories (Brief 18). ISO 3166-1 alpha-2 + English name.
# Must stay in step with frontend/src/sync/constants.js.
COUNTRIES = {
    "US": "United States", "CA": "Canada", "GB": "United Kingdom", "AU": "Australia", "DE": "Germany",
    "FR": "France", "IE": "Ireland", "NL": "Netherlands", "ES": "Spain", "IT": "Italy", "SE": "Sweden",
    "NO": "Norway", "DK": "Denmark", "FI": "Finland", "BE": "Belgium", "AT": "Austria", "CH": "Switzerland",
    "PT": "Portugal", "PL": "Poland", "NZ": "New Zealand", "JP": "Japan", "KR": "South Korea",
    "SG": "Singapore", "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "ZA": "South Africa",
    "IN": "India", "AE": "United Arab Emirates", "HK": "Hong Kong",
}
