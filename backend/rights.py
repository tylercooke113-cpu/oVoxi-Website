"""Rights (splits) for every upload. See docs/PRD-02 sections 3, 4 and 10,
and docs/PRD-03 section 4.1 (check 1).

Shares are integer basis points: 10000 = 100.00%. Never floats.
"""
import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sync_constants import (
    IPI_PATTERN, MAX_PARTIES, PRO_ORGS, PUBLISHER_ROLES, TOTAL_BP, WRITER_ROLES,
)

SIDE_LABELS = {
    "writers": "Writers",
    "publishers": "Publishers",
    "master_owners": "Master owners",
}
DEFAULT_ROLES = {"writers": "CA", "publishers": "E", "master_owners": None}
ALLOWED_ROLES = {"writers": WRITER_ROLES, "publishers": PUBLISHER_ROLES, "master_owners": ()}


def _pct(bp: int) -> str:
    return f"{bp / 100:.2f}".rstrip("0").rstrip(".")


class RightsPartyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str = Field(..., max_length=120)
    share_bp: int = Field(..., ge=1, le=TOTAL_BP)
    role: Optional[str] = None
    society: Optional[str] = None
    ipi_name_number: Optional[str] = None

    @field_validator("legal_name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Every party needs a legal name.")
        return v

    @field_validator("society")
    @classmethod
    def _society(cls, v):
        if v in (None, ""):
            return None
        if v not in PRO_ORGS:
            raise ValueError("Invalid PRO.")
        return v

    @field_validator("ipi_name_number")
    @classmethod
    def _ipi(cls, v):
        if v in (None, ""):
            return None
        if not re.fullmatch(IPI_PATTERN, v):
            raise ValueError("IPI must be 9 or 11 digits.")
        return v


class TrackRightsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owns_everything: bool = False
    self_legal_name: str = Field(..., max_length=120)
    writers: List[RightsPartyIn] = []
    publishers: List[RightsPartyIn] = []
    master_owners: List[RightsPartyIn] = []
    attested: bool

    @field_validator("self_legal_name")
    @classmethod
    def _self_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Enter your legal name.")
        return v

    @field_validator("attested")
    @classmethod
    def _attested(cls, v):
        if not v:
            raise ValueError("Confirm the splits to use sync.")
        return v

    @model_validator(mode="after")
    def _lists(self):
        if self.owns_everything:
            if self.writers or self.publishers or self.master_owners:
                raise ValueError("Leave the splits empty when you own 100%.")
            return self
        for side, label in SIDE_LABELS.items():
            parties = getattr(self, side)
            if not 1 <= len(parties) <= MAX_PARTIES:
                raise ValueError(f"{label} need 1 to {MAX_PARTIES} parties.")
            total = sum(p.share_bp for p in parties)
            if total != TOTAL_BP:
                gap = abs(TOTAL_BP - total)
                where = "short" if total < TOTAL_BP else "over"
                raise ValueError(f"{label} add up to {_pct(total)}%, {_pct(gap)}% {where}.")
            names = [p.legal_name.casefold() for p in parties]
            if len(set(names)) != len(names):
                raise ValueError(f"{label} list the same name twice.")
            for p in parties:
                if p.role is not None and p.role not in ALLOWED_ROLES[side]:
                    raise ValueError(f"Invalid role for {label.lower()}.")
        return self


def _party(p: RightsPartyIn, side: str, self_name: str) -> dict:
    return {
        "legal_name": p.legal_name,
        "ipi_name_number": p.ipi_name_number,
        "society": p.society,
        "role": p.role if side != "master_owners" else None,
        "share_bp": p.share_bp,
        "is_self": p.legal_name.casefold() == self_name.casefold(),
    }


def build_rights(rights: TrackRightsIn, *, intake, clerk_user_id: str, now_iso: str) -> dict:
    """Return the `rights` document to store. PRD-02 rule 6: the shortcut is
    expanded here into three full lists, never stored empty.

    `intake` is the validated SyncIntake, or None on uploads without sync.
    When it says the artist is PRO-affiliated, their PRO and IPI go on the self
    writer row only: a writer IPI is personal and is not the publisher's IPI.
    """
    name = rights.self_legal_name
    if rights.owns_everything:
        affiliated = intake is not None and not intake.pro_not_affiliated
        lists = {
            "writers": [{
                "legal_name": name,
                "ipi_name_number": intake.ipi if affiliated else None,
                "society": intake.pro_name if affiliated else None,
                "role": DEFAULT_ROLES["writers"],
                "share_bp": TOTAL_BP,
                "is_self": True,
            }],
            "publishers": [{
                "legal_name": name, "ipi_name_number": None, "society": None,
                "role": DEFAULT_ROLES["publishers"], "share_bp": TOTAL_BP, "is_self": True,
            }],
            "master_owners": [{
                "legal_name": name, "ipi_name_number": None, "society": None,
                "role": None, "share_bp": TOTAL_BP, "is_self": True,
            }],
        }
    else:
        lists = {
            side: [_party(p, side, name) for p in getattr(rights, side)]
            for side in SIDE_LABELS
        }
    return {
        "owns_everything": rights.owns_everything,
        **lists,
        "attested_at": now_iso,
        "attested_by_clerk_user_id": clerk_user_id,
    }
