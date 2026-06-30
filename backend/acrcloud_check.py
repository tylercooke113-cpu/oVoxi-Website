"""
ACRCloud chain-of-title scan helper.
Synchronous — call via asyncio.to_thread in the pipeline.
"""

import json
import logging
import os
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


def scan_file(file_path: str) -> dict:
    try:
        raw = _get_recognizer().recognize_by_file(file_path, 0, 15)
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
