"""
ACRCloud chain-of-title scan helper.
Synchronous — call via asyncio.to_thread in the pipeline.
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_recognizer = None


def _get_recognizer():
    global _recognizer
    if _recognizer is None:
        from acrcloud.recognizer import ACRCloudRecognizer
        _recognizer = ACRCloudRecognizer({
            "host": os.environ["ACRCLOUD_HOST"],
            "access_key": os.environ["ACRCLOUD_ACCESS_KEY"],
            "access_secret": os.environ["ACRCLOUD_ACCESS_SECRET"],
            "timeout": 15,
        })
    return _recognizer


def _result(
    status: str,
    raw_code: Optional[int] = None,
    matched_title: Optional[str] = None,
    matched_artist: Optional[str] = None,
    matched_label: Optional[str] = None,
    matched_isrc: Optional[str] = None,
    confidence: Optional[int] = None,
    acrid: Optional[str] = None,
) -> dict:
    return {
        "status": status,
        "matched_title": matched_title,
        "matched_artist": matched_artist,
        "matched_label": matched_label,
        "matched_isrc": matched_isrc,
        "confidence": confidence,
        "acrid": acrid,
        "raw_code": raw_code,
    }


# Brief 25b: scan the whole song, not only its first 15 seconds, so a sample later in
# the track is caught. One request per window: about 7 for a 3-minute song at the
# defaults. Tune with ACR_SCAN_STEP_SECONDS / ACR_SCAN_WINDOW_SECONDS / ACR_SCAN_MAX_WINDOWS.
# ACR_SCAN_PAUSE_SECONDS spaces the requests so one song stays under the plan's
# requests-per-second limit (2 on the Free plan).
_SEVERITY = {"CONFLICT": 3, "NEEDS_DOCS": 2, "SCAN_ERROR": 1, "CLEARED": 0}


def scan_offsets(duration_s: Optional[float]) -> list:
    step = max(5, int(os.environ.get("ACR_SCAN_STEP_SECONDS", "30")))
    cap = max(1, int(os.environ.get("ACR_SCAN_MAX_WINDOWS", "30")))
    if not duration_s or duration_s <= 15:
        return [0]
    return list(range(0, int(duration_s) - 5, step))[:cap]


def scan_file(file_path: str, duration_s: Optional[float] = None) -> dict:
    """Scan every window across the song and return the most serious result:
    CONFLICT, then NEEDS_DOCS, then SCAN_ERROR, else CLEARED. A match carries its offset."""
    worst = None
    pause = max(0.0, float(os.environ.get("ACR_SCAN_PAUSE_SECONDS", "0.6")))
    for i, offset in enumerate(scan_offsets(duration_s)):
        if i and pause:
            time.sleep(pause)
        r = scan_window(file_path, offset)
        if worst is None or _SEVERITY[r["status"]] > _SEVERITY[worst["status"]]:
            worst = {**r, "matched_offset_s": offset if r["status"] in ("CONFLICT", "NEEDS_DOCS") else None}
        if worst["status"] == "CONFLICT":
            break                                  # nothing is more serious; save requests
    return worst


def scan_window(file_path: str, offset_s: int = 0) -> dict:
    length = int(os.environ.get("ACR_SCAN_WINDOW_SECONDS", "12"))
    try:
        raw = _get_recognizer().recognize_by_file(file_path, offset_s, length)
        data = json.loads(raw)
    except Exception as exc:
        logger.error("ACRCloud scan failed for %s: %s", file_path, exc)
        return _result("SCAN_ERROR")

    status_obj = data.get("status", {})
    code = status_obj.get("code")

    if code == 1001:
        return _result("CLEARED", raw_code=1001)

    if code == 0:
        music = data.get("metadata", {}).get("music", [])
        if not music:
            logger.warning("ACRCloud code=0 but no music entries for %s", file_path)
            return _result("SCAN_ERROR", raw_code=0)

        top = music[0]
        score = top.get("score", 0)

        artists = top.get("artists", [])
        matched_artist = artists[0].get("name") if artists else None

        label_raw = top.get("label", "")
        matched_label = label_raw.get("name") if isinstance(label_raw, dict) else (label_raw or None)

        acr_status = "CONFLICT" if score >= 90 else ("NEEDS_DOCS" if score >= 70 else "CLEARED")

        if acr_status in ("CONFLICT", "NEEDS_DOCS"):
            return _result(
                acr_status,
                raw_code=0,
                matched_title=top.get("title"),
                matched_artist=matched_artist,
                matched_label=matched_label,
                matched_isrc=top.get("external_ids", {}).get("isrc"),
                confidence=score,
                acrid=top.get("acrid"),
            )
        return _result("CLEARED", raw_code=0)

    logger.warning("ACRCloud unexpected code=%s msg=%s", code, status_obj.get("msg"))
    return _result("SCAN_ERROR", raw_code=code)
