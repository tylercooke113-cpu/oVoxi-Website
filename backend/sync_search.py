"""Sync library search. See docs/PRD-03 section 6.1, decisions 21 and 22.

The ONLY place that builds library queries, so a later move to Atlas Search
or Typesense changes this one file. Pure: builds filters and pipelines, parses
and encodes cursors. No DB access.
"""
import base64
import json
from dataclasses import dataclass, field
from typing import Mapping, Optional

from sync_constants import BPM_MAX, BPM_MIN, GENRES, MOODS, VOCALS
from sync_public import LISTING_FILTER

PAGE_SIZE = 25
MAX_DURATION_S = 900
SORTS = ("newest", "popular")


class SearchParamError(ValueError):
    pass


@dataclass
class LibraryQuery:
    genres: list = field(default_factory=list)
    moods: list = field(default_factory=list)
    bpm: Optional[tuple] = None
    vocals: Optional[str] = None
    duration: Optional[tuple] = None
    sort: Optional[str] = None           # None: server picks the default
    cursor: Optional[dict] = None


def _list(raw: Optional[str], allowed, label) -> list:
    if not raw:
        return []
    values = [v for v in raw.split(",") if v]
    for v in values:
        if v not in allowed:
            raise SearchParamError(f"Unknown {label}: {v}")
    if len(values) > len(allowed):
        raise SearchParamError(f"Too many {label} values")
    return sorted(set(values))


def _range(raw: Optional[str], lo: float, hi: float, label: str) -> Optional[tuple]:
    if not raw:
        return None
    try:
        a, b = raw.split("-", 1)
        a = float(a) if a else lo
        b = float(b) if b else hi
    except ValueError:
        raise SearchParamError(f"{label} must look like 80-100")
    if not (lo <= a <= hi and lo <= b <= hi and a <= b):
        raise SearchParamError(f"{label} must be between {int(lo)} and {int(hi)}")
    return (a, b)


def encode_cursor(sort: str, row: dict) -> str:
    payload = {"s": sort, "t": row.get("sync_listed_at") or "", "i": row["id"]}
    if sort == "popular":
        payload["n"] = int(row.get("artist_sales") or 0)
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(raw: Optional[str], sort: str) -> Optional[dict]:
    if not raw:
        return None
    try:
        c = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        assert isinstance(c, dict) and c.get("s") == sort
        assert isinstance(c.get("t"), str) and isinstance(c.get("i"), str)
        if sort == "popular":
            assert isinstance(c.get("n"), int) and c["n"] >= 0
        return c
    except Exception:
        raise SearchParamError("Invalid page cursor")


def parse_params(params: Mapping) -> LibraryQuery:
    sort = params.get("sort") or None
    if sort is not None and sort not in SORTS:
        raise SearchParamError("Sort must be newest or popular")
    vocals = params.get("vocals") or None
    if vocals is not None and vocals not in VOCALS:
        raise SearchParamError("Vocals must be vocal or instrumental")
    q = LibraryQuery(
        genres=_list(params.get("genre"), GENRES, "genre"),
        moods=_list(params.get("mood"), MOODS, "mood"),
        bpm=_range(params.get("bpm"), BPM_MIN, BPM_MAX, "BPM"),
        vocals=vocals,
        duration=_range(params.get("length"), 0, MAX_DURATION_S, "Length"),
        sort=sort,
    )
    if params.get("cursor") and not sort:
        raise SearchParamError("A page cursor needs a sort")
    q.cursor = decode_cursor(params.get("cursor"), sort) if sort else None
    return q


def build_filter(q: LibraryQuery) -> dict:
    """Listing rule (PRD-03 3.2) AND every chosen filter. Within genre or mood: any."""
    f = dict(LISTING_FILTER)
    if q.genres:
        f["genre"] = {"$in": q.genres}
    if q.moods:
        f["metadata.moods"] = {"$in": q.moods}
    if q.bpm:
        f["metadata.bpm"] = {"$gte": q.bpm[0], "$lte": q.bpm[1]}
    if q.vocals:
        f["metadata.vocals"] = q.vocals
    if q.duration:
        f["metadata.duration_s"] = {"$gte": q.duration[0], "$lte": q.duration[1]}
    return f


def _after_cursor(sort: str, c: dict) -> dict:
    """Rows strictly after the cursor in (artist_sales desc,) listed desc, id desc order."""
    t, i = c["t"], c["i"]
    newer = [{"_listed": {"$lt": t}}, {"_listed": t, "id": {"$lt": i}}]
    if sort == "newest":
        return {"$or": newer}
    n = c["n"]
    return {"$or": [{"artist_sales": {"$lt": n}},
                    {"artist_sales": n, "$or": newer}]}


def build_pipeline(q: LibraryQuery, sort: str, limit: int = PAGE_SIZE) -> list:
    """Aggregation: listed tracks + their artist profile, sorted, one page (+1 to
    know whether there is a next page)."""
    pipeline = [
        {"$match": build_filter(q)},
        {"$lookup": {"from": "sync_profiles", "localField": "clerk_user_id",
                     "foreignField": "user_id", "as": "_profiles"}},
        # _profiles is [] or [profile] (user_id is unique). $max over it gives the
        # artist's sales, or null (then 0) when the artist has no profile.
        {"$addFields": {
            "artist_sales": {"$ifNull": [{"$max": "$_profiles.sales_count"}, 0]},
            "_listed": {"$ifNull": ["$sync_listed_at", ""]},
        }},
    ]
    if q.cursor:
        pipeline.append({"$match": _after_cursor(sort, q.cursor)})
    order = {"_listed": -1, "id": -1}
    if sort == "popular":
        order = {"artist_sales": -1, **order}
    pipeline += [{"$sort": order}, {"$limit": limit + 1}]
    return pipeline
