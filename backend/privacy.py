"""Privacy choices (Brief 26). Append-only, like the consent ledger: every change
is a new row in `privacy_choices`. There is no update or delete function.

Categories: essential (always on, not stored), analytics (PostHog analytics and
session replay), advertising (selling or sharing personal information). A Global
Privacy Control signal always forces advertising off.
"""
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SOURCES = ("prompt", "gpc", "account", "signup", "privacy_choices")
VISITOR_ID_PATTERN = r"^[A-Za-z0-9-]{8,64}$"
POLICY_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
USER_AGENT_MAX = 300


class PrivacyChoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analytics: bool
    advertising: bool
    gpc: bool = False
    source: str
    policy_date: str
    visitor_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator("source")
    @classmethod
    def _source(cls, v):
        if v not in SOURCES:
            raise ValueError("Invalid source.")
        return v

    @field_validator("policy_date")
    @classmethod
    def _policy_date(cls, v):
        if not re.fullmatch(POLICY_DATE_PATTERN, v):
            raise ValueError("Invalid policy date.")
        return v

    @field_validator("visitor_id")
    @classmethod
    def _visitor_id(cls, v):
        if v in (None, ""):
            return None
        if not re.fullmatch(VISITOR_ID_PATTERN, v):
            raise ValueError("Invalid visitor id.")
        return v


def choice_row(choice: PrivacyChoiceIn, *, user_id: Optional[str], ip: str,
               user_agent: str, now: Optional[datetime] = None) -> dict:
    """The row to append. GPC forces advertising off whatever was sent."""
    now = now or datetime.now(timezone.utc)
    return {
        "user_id": user_id,
        "visitor_id": choice.visitor_id,
        "analytics": choice.analytics,
        "advertising": False if choice.gpc else choice.advertising,
        "gpc": choice.gpc,
        "source": choice.source,
        "policy_date": choice.policy_date,
        "ip": ip,
        "user_agent": (user_agent or "")[:USER_AGENT_MAX],
        "created_at": now.isoformat(),
    }


def public_choice(row: Optional[dict]) -> Optional[dict]:
    """What the account owner sees. No IP, user agent or visitor id."""
    if not row:
        return None
    return {k: row.get(k) for k in ("analytics", "advertising", "gpc", "source",
                                    "policy_date", "created_at")}


def clerk_privacy(row: dict) -> dict:
    """The copy kept in Clerk public_metadata.privacy."""
    return {"analytics": row["analytics"], "advertising": row["advertising"],
            "policy_date": row["policy_date"], "updated_at": row["created_at"]}


async def record_choice(db, row: dict) -> None:
    await db.privacy_choices.insert_one(dict(row))


async def latest_choice(db, user_id: str) -> Optional[dict]:
    return await db.privacy_choices.find_one(
        {"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)])
