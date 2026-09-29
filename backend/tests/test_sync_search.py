"""
PRD-03 Phase 5: the sync library search (sync_search.py) and GET /api/sync/tracks.

The aggregation pipeline is executed for real against mongomock (an in-memory
MongoDB), so filters, the profile join, both sorts and cursor paging are
tested end to end, not just built. Requires mongomock (requirements-dev.txt).
"""
import pytest
from fastapi.testclient import TestClient

mongomock = pytest.importorskip("mongomock")

import server  # noqa: E402
from sync_constants import GENRES  # noqa: E402
from sync_search import (  # noqa: E402
    PAGE_SIZE, SearchParamError, build_pipeline, decode_cursor, encode_cursor, parse_params,
)


def track(i, **over):
    doc = {
        "id": f"t{i:03d}", "clerk_user_id": over.pop("uid", "u1"), "track_name": f"Track {i}",
        "artist_name": "Upload Name", "genre": "R&B", "status": "completed",
        "consent": {"ai_training": False, "sync": True}, "intake": {"content_id": "no", "ipi": "00123456789"},
        "sync_status": "cleared", "on_sync_profile": True,
        "sync_listed_at": f"2026-09-{(i % 28) + 1:02d}T00:00:{i % 60:02d}+00:00",
        "metadata": {"moods": ["Chill"], "vocals": "vocal", "bpm": 90.0, "key": "C major", "duration_s": 180.0},
        "preview_key": "catalog/x.mp3", "waveform_key": "catalog/x.json",
        "matched_title": "Famous Song",
    }
    for k, v in over.items():
        if k.startswith("meta_"):
            doc["metadata"][k[5:]] = v
        else:
            doc[k] = v
    return doc


class AsyncCol:
    def __init__(self, col):
        self.col = col

    async def find_one(self, *a, **k):
        return self.col.find_one(*a, **k)

    async def count_documents(self, *a, **k):
        return self.col.count_documents(*a, **k)

    def aggregate(self, pipeline):
        rows = list(self.col.aggregate(pipeline))

        class Cur:
            async def to_list(self, n):
                return rows[:n]
        return Cur()


@pytest.fixture
def mdb():
    return mongomock.MongoClient().db


def run(mdb, params, sort=None):
    q = parse_params(params)
    return list(mdb.track_submissions.aggregate(build_pipeline(q, sort or q.sort or "newest")))


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

def test_genres_match_upload_list():
    assert set(GENRES) == server.VALID_GENRES


@pytest.mark.parametrize("params", [
    {"genre": "Polka"}, {"mood": "Angry"}, {"bpm": "10-100"}, {"bpm": "100-80"}, {"bpm": "abc"},
    {"length": "0-2000"}, {"vocals": "choir"}, {"sort": "random"},
    {"cursor": "abc"}, {"cursor": "abc", "sort": "newest"},
])
def test_bad_params_rejected(params):
    with pytest.raises(SearchParamError):
        parse_params(params)


def test_params_parsed():
    q = parse_params({"genre": "R&B,Soul,R&B", "mood": "Chill", "bpm": "80-100",
                      "vocals": "instrumental", "length": "60-", "sort": "newest"})
    assert q.genres == ["R&B", "Soul"] and q.moods == ["Chill"]
    assert q.bpm == (80.0, 100.0) and q.duration == (60.0, 900.0) and q.vocals == "instrumental"


def test_cursor_round_trip_and_sort_mismatch():
    c = encode_cursor("popular", {"id": "t1", "sync_listed_at": "2026", "artist_sales": 3})
    assert decode_cursor(c, "popular") == {"s": "popular", "t": "2026", "i": "t1", "n": 3}
    with pytest.raises(SearchParamError):
        decode_cursor(c, "newest")


# ---------------------------------------------------------------------------
# Listing rule and filters, executed
# ---------------------------------------------------------------------------

def test_only_listed_tracks(mdb):
    mdb.track_submissions.insert_many([
        track(1), track(2, sync_status="needs_docs"), track(3, on_sync_profile=False),
        track(4, consent={"sync": False}), track(5, intake={"content_id": "yes"}),
        track(6, sync_delisted_by_admin=True),
    ])
    assert [r["id"] for r in run(mdb, {})] == ["t001"]


def test_genre_any_mood_any_and_across(mdb):
    mdb.track_submissions.insert_many([
        track(1, genre="R&B", meta_moods=["Chill"]),
        track(2, genre="Soul", meta_moods=["Sad"]),
        track(3, genre="Trap", meta_moods=["Chill"]),
        track(4, genre="Soul", meta_moods=["Chill", "Dreamy"]),
    ])
    ids = lambda p: sorted(r["id"] for r in run(mdb, p))
    assert ids({"genre": "R&B,Soul"}) == ["t001", "t002", "t004"]          # any within genre
    assert ids({"mood": "Sad,Dreamy"}) == ["t002", "t004"]                 # any within mood
    assert ids({"genre": "R&B,Soul", "mood": "Chill"}) == ["t001", "t004"] # all across groups


def test_bpm_vocals_length_filters(mdb):
    mdb.track_submissions.insert_many([
        track(1, meta_bpm=85.0, meta_vocals="vocal", meta_duration_s=45.0),
        track(2, meta_bpm=100.0, meta_vocals="instrumental", meta_duration_s=150.0),
        track(3, meta_bpm=130.0, meta_vocals="instrumental", meta_duration_s=240.0),
    ])
    ids = lambda p: sorted(r["id"] for r in run(mdb, p))
    assert ids({"bpm": "80-100"}) == ["t001", "t002"]                      # inclusive edges
    assert ids({"vocals": "instrumental"}) == ["t002", "t003"]
    assert ids({"length": "0-60"}) == ["t001"]
    assert ids({"bpm": "90-140", "vocals": "instrumental", "length": "180-"}) == ["t003"]


# ---------------------------------------------------------------------------
# Sorting and paging, executed
# ---------------------------------------------------------------------------

def page_all(mdb, sort):
    seen, cursor = [], None
    while True:
        params = {"sort": sort, **({"cursor": cursor} if cursor else {})}
        rows = run(mdb, params)
        page, more = rows[:PAGE_SIZE], len(rows) > PAGE_SIZE
        seen += [r["id"] for r in page]
        if not more:
            return seen
        cursor = encode_cursor(sort, page[-1])


def test_newest_paging_covers_everything_once_in_order(mdb):
    mdb.track_submissions.insert_many([track(i) for i in range(1, 61)])
    seen = page_all(mdb, "newest")
    assert len(seen) == 60 and len(set(seen)) == 60
    docs = {d["id"]: d for d in mdb.track_submissions.find()}
    keys = [(docs[i]["sync_listed_at"], i) for i in seen]
    assert keys == sorted(keys, reverse=True)


def test_popular_orders_by_artist_sales_then_newest_and_pages(mdb):
    mdb.sync_profiles.insert_many([
        {"user_id": "big", "slug": "big", "display_name": "Big Seller", "sales_count": 9},
        {"user_id": "mid", "slug": "mid", "display_name": "Mid", "sales_count": 2},
    ])
    mdb.track_submissions.insert_many(
        [track(i, uid="big") for i in range(1, 21)]
        + [track(i, uid="mid") for i in range(21, 41)]
        + [track(i, uid="none") for i in range(41, 61)])     # no profile: 0 sales
    seen = page_all(mdb, "popular")
    assert len(seen) == 60 and len(set(seen)) == 60
    owner = {d["id"]: d["clerk_user_id"] for d in mdb.track_submissions.find()}
    groups = [owner[i] for i in seen]
    assert groups == ["big"] * 20 + ["mid"] * 20 + ["none"] * 20


def test_profile_joined_for_display_name(mdb):
    mdb.sync_profiles.insert_one({"user_id": "u1", "slug": "tyler", "display_name": "Tyler Example", "sales_count": 0})
    mdb.track_submissions.insert_one(track(1))
    row = run(mdb, {})[0]
    assert row["_profiles"][0]["display_name"] == "Tyler Example" and row["artist_sales"] == 0


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@pytest.fixture
def api(mdb, monkeypatch):
    fake = type("DB", (), {})()
    fake.track_submissions = AsyncCol(mdb.track_submissions)
    fake.sync_profiles = AsyncCol(mdb.sync_profiles)
    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setattr(server.limiter, "enabled", False)
    monkeypatch.setenv("SYNC_LIBRARY_ENABLED", "false")
    state = {"viewer": None}
    server.app.dependency_overrides[server.optional_clerk] = lambda: state["viewer"]

    def as_admin(yes=True):
        state["viewer"] = {"sub": "admin", "metadata": {"role": "admin"}} if yes else None
    yield TestClient(server.app), mdb, as_admin, monkeypatch
    server.app.dependency_overrides.clear()


def test_gate(api):
    client, mdb, as_admin, mp = api
    mdb.track_submissions.insert_one(track(1))
    assert client.get("/api/sync/tracks").status_code == 404                  # public, gate off
    for v in ("True", "1", "yes"):
        mp.setenv("SYNC_LIBRARY_ENABLED", v)
        assert client.get("/api/sync/tracks").status_code == 404
    mp.setenv("SYNC_LIBRARY_ENABLED", "false")
    as_admin()
    body = client.get("/api/sync/tracks").json()                              # admin preview
    assert body["viewer"] == {"is_admin": True, "public": False}
    mp.setenv("SYNC_LIBRARY_ENABLED", "true")
    as_admin(False)
    assert client.get("/api/sync/tracks").status_code == 200                  # public, gate on


def test_artist_page_switch_does_not_open_library(api):
    client, mdb, as_admin, mp = api
    mp.setenv("SYNC_PUBLIC_PAGES_ENABLED", "true")
    assert client.get("/api/sync/tracks").status_code == 404


def test_default_sort_newest_until_first_sale(api):
    client, mdb, as_admin, mp = api
    mp.setenv("SYNC_LIBRARY_ENABLED", "true")
    mdb.sync_profiles.insert_one({"user_id": "u1", "slug": "a", "display_name": "A", "sales_count": 0})
    mdb.track_submissions.insert_one(track(1))
    assert client.get("/api/sync/tracks").json()["sort"] == "newest"
    mdb.sync_profiles.update_one({"user_id": "u1"}, {"$set": {"sales_count": 1}})
    assert client.get("/api/sync/tracks").json()["sort"] == "popular"
    assert client.get("/api/sync/tracks?sort=newest").json()["sort"] == "newest"


def test_response_allowlist_total_and_paging(api):
    client, mdb, as_admin, mp = api
    mp.setenv("SYNC_LIBRARY_ENABLED", "true")
    mdb.track_submissions.insert_many([track(i) for i in range(1, 31)])
    first = client.get("/api/sync/tracks?sort=newest").json()
    assert first["total"] == 30 and len(first["tracks"]) == 25 and first["next_cursor"]
    assert set(first["tracks"][0]) == {"id", "track_name", "artist_display_name", "artist_slug", "genre",
                                       "moods", "vocals", "bpm", "key", "duration_s", "has_preview", "has_waveform"}
    text = str(first)
    for s in ("Famous Song", "00123456789", "clerk_user_id", "catalog/", "u1", "_profiles", "artist_sales"):
        assert s not in text, s
    second = client.get(f"/api/sync/tracks?sort=newest&cursor={first['next_cursor']}").json()
    assert len(second["tracks"]) == 5 and second["next_cursor"] is None and second["total"] is None
    assert not {t["id"] for t in first["tracks"]} & {t["id"] for t in second["tracks"]}


def test_bad_params_are_422(api):
    client, mdb, as_admin, mp = api
    mp.setenv("SYNC_LIBRARY_ENABLED", "true")
    resp = client.get("/api/sync/tracks?genre=Polka")
    assert resp.status_code == 422 and "Unknown genre" in resp.json()["detail"]
