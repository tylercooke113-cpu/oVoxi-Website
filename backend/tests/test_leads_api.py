"""Backend API tests for oVoxi leads endpoint."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001').rstrip('/')
API = f"{BASE_URL}/api"

INTEREST_VALUES = ["ai_company", "enterprise", "artist", "investor", "other"]


@pytest.fixture
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ----- Health -----
class TestHealth:
    def test_root(self, api_client):
        r = api_client.get(f"{API}/")
        assert r.status_code == 200
        assert "message" in r.json()


# ----- POST /api/leads happy path for all 5 interest values -----
class TestLeadCreation:
    @pytest.mark.parametrize("interest", INTEREST_VALUES)
    def test_create_lead_each_interest(self, api_client, interest):
        payload = {
            "name": f"TEST_User_{interest}",
            "email": f"test_{interest}@example.com",
            "company": f"TEST_Company_{interest}",
            "interest": interest,
            "message": f"Test message for {interest} interest type.",
        }
        r = api_client.post(f"{API}/leads", json=payload)
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        data = r.json()
        assert "id" in data and isinstance(data["id"], str) and len(data["id"]) > 0
        assert "created_at" in data
        assert data["name"] == payload["name"]
        assert data["email"] == payload["email"]
        assert data["company"] == payload["company"]
        assert data["interest"] == interest
        assert data["message"] == payload["message"]
        # No _id leaked
        assert "_id" not in data

    def test_create_lead_without_company(self, api_client):
        payload = {
            "name": "TEST_NoCompany",
            "email": "no_company@example.com",
            "interest": "artist",
            "message": "No company optional field test.",
        }
        r = api_client.post(f"{API}/leads", json=payload)
        assert r.status_code == 201
        d = r.json()
        assert d["company"] is None


# ----- Validation -----
class TestLeadValidation:
    def test_invalid_email_returns_422(self, api_client):
        r = api_client.post(f"{API}/leads", json={
            "name": "TEST_BadEmail",
            "email": "not-an-email",
            "interest": "investor",
            "message": "msg",
        })
        assert r.status_code == 422

    @pytest.mark.parametrize("missing_field", ["name", "email", "interest", "message"])
    def test_missing_required_field_returns_422(self, api_client, missing_field):
        payload = {
            "name": "TEST_X",
            "email": "x@example.com",
            "interest": "other",
            "message": "msg",
        }
        payload.pop(missing_field)
        r = api_client.post(f"{API}/leads", json=payload)
        assert r.status_code == 422, f"Expected 422 when missing {missing_field}, got {r.status_code}"

    def test_empty_name_returns_422(self, api_client):
        r = api_client.post(f"{API}/leads", json={
            "name": "",
            "email": "x@example.com",
            "interest": "other",
            "message": "msg",
        })
        assert r.status_code == 422

    def test_empty_message_returns_422(self, api_client):
        r = api_client.post(f"{API}/leads", json={
            "name": "TEST_X",
            "email": "x@example.com",
            "interest": "other",
            "message": "",
        })
        assert r.status_code == 422


# ----- GET /api/leads -----
class TestLeadList:
    def test_list_leads_sorted_desc_and_no_mongo_id(self, api_client):
        # Create a marker lead
        marker_payload = {
            "name": "TEST_SortMarker",
            "email": "sortmarker@example.com",
            "interest": "investor",
            "message": "sort marker",
        }
        cr = api_client.post(f"{API}/leads", json=marker_payload)
        assert cr.status_code == 201
        created_id = cr.json()["id"]

        r = api_client.get(f"{API}/leads")
        assert r.status_code == 200
        leads = r.json()
        assert isinstance(leads, list)
        assert len(leads) >= 1
        # No _id leaked anywhere
        for ld in leads:
            assert "_id" not in ld
            assert "id" in ld and "created_at" in ld
        # Most recent lead with our marker email should be present
        ids = [ld["id"] for ld in leads]
        assert created_id in ids

        # Verify sort order desc by created_at
        timestamps = [ld["created_at"] for ld in leads]
        assert timestamps == sorted(timestamps, reverse=True), "leads not sorted by created_at desc"
