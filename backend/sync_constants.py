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

SAMPLE_DECLARATIONS = ("original", "cleared_sample", "royalty_free_loop")   # every value ever stored

# Brief 25b (Agreement 3.6): samples of other recordings are not allowed at all. A song
# with royalty-free loops may be offered for sync only, after each loop creator is listed
# in the splits and consents, and Tyler approves each loop license.
UPLOAD_SAMPLE_CHOICES = ("original", "royalty_free_loop")
MAX_LOOPS = 4
LOOP_SOURCES = ("Splice", "Loopmasters / Loopcloud", "Producer directly", "Other")
LOOP_LICENSE_TYPES = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}
LOOP_LICENSE_MAX_BYTES = 10 * 1024 * 1024
SAMPLES_NOT_ALLOWED_MESSAGE = "Songs that sample other recordings can't be uploaded."
PRO_REQUIRED_MESSAGE = ("Sync placements need a performing rights organization (PRO). "
                        "You can still offer this song for AI training.")
SYNC_SOLE_MESSAGE = "Confirm this song is not offered for sync anywhere else."
LOOPS_NO_AI_MESSAGE = ("Songs with loops or samples can't be offered for AI training. Most loop and "
                       "sample licenses, including Splice and Loopmasters, don't allow it.")

# AI-tools disclosure (Brief 25b Part D1, Agreement 9(e)). "full" is refused at upload;
# "partial" needs an admin review before the track clears.
AI_TOOLS = ("none", "assistive", "partial", "full")
AI_TOOLS_PASS = ("none", "assistive")
AI_TOOLS_DETAIL_MAX = 300
AI_TOOLS_FULL_MESSAGE = "OVOXI licenses music created by people. Songs made mostly with AI can't be uploaded."

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

# Human labels for the role codes above. Must stay in step with the label text in
# frontend/src/sync/constants.js. Used to render co-owner interest lines (cosign.py).
WRITER_ROLE_LABELS = {
    "CA": "Composer & lyricist", "C": "Composer", "A": "Lyricist",
    "AR": "Arranger", "AD": "Adaptor", "TR": "Translator",
}
PUBLISHER_ROLE_LABELS = {
    "E": "Original publisher", "AM": "Administrator",
    "SE": "Sub-publisher", "PA": "Income participant",
}

# Co-owner Consent (Brief 22, Part C).
COSIGN_TOKEN_TTL_DAYS = 30
COSIGN_MAX_RESENDS = 5          # total times one request's link may be resent
COSIGN_RESEND_COOLDOWN_MIN = 60  # minimum minutes between resends of one request
EMAIL_MAX_LENGTH = 254

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

# Subscription plans (Brief 19). Monthly/annual cents are display values that mirror the
# Stripe prices; the server never charges from them (the setup script verifies they match).
# Caps are server-side policy. Must stay in step with frontend/src/sync/constants.js.
PLANS = {
    "creator":  {"label": "Creator",  "month_cents": 1900,  "year_cents": 19000,  "month_cap": 100},
    "pro":      {"label": "Pro",       "month_cents": 4900,  "year_cents": 49000,  "month_cap": 300},
    "business": {"label": "Business",  "month_cents": 14900, "year_cents": 149000, "month_cap": 1000},
}
SUB_DAY_CAP = 50
