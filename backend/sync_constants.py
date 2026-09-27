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

# IPI name numbers are up to 11 digits. Deliberately loose.
IPI_PATTERN = r"^\d{9,11}$"
