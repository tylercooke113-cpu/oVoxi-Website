import os
import sys
from unittest.mock import MagicMock

# Mock packages unavailable or version-incompatible outside the Docker build.
# motor.motor_asyncio is mocked because pymongo latest is incompatible with
# motor 3.3.1 in this test environment; the auth tests never touch the DB.
_mock_motor = MagicMock()
for _mod in ["modal", "matchering", "pyacrcloud", "acrcloud_check",
             "motor", "motor.motor_asyncio"]:
    sys.modules.setdefault(_mod, MagicMock())
sys.modules["motor.motor_asyncio"] = _mock_motor

# Env vars required by server.py at module load time.
_DEFAULTS = {
    "CLERK_JWKS_URL": "https://clerk.test/.well-known/jwks.json",
    "CLERK_ISSUER": "https://clerk.test",
    "CLERK_AUTHORIZED_PARTIES": "https://app.test",
    "MONGO_URL": "mongodb://localhost:27017",
    "DB_NAME": "ovoxi_test",
    "R2_ENDPOINT": "https://r2.test",
    "R2_ACCESS_KEY_ID": "test_key",
    "R2_SECRET_ACCESS_KEY": "test_secret",
    "R2_BUCKET_NAME": "test_bucket",
}
for _k, _v in _DEFAULTS.items():
    os.environ.setdefault(_k, _v)
