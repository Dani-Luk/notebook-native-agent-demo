from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class SafetyDecision:
    mode: str
    reasons: List[str]


def classify_execution(code: str) -> SafetyDecision:
    text = (code or "").lower()
    reasons: List[str] = []

    manual_markers = [
        "pip install",
        "conda install",
        "subprocess",
        "os.system",
        "!pip",
        "!apt",
        "open(",
        ".to_csv(",
        ".to_excel(",
        "requests.",
        "httpx.",
        "urllib.",
        "socket.",
        "shutil.rmtree",
        "rm -rf",
    ]
    for marker in manual_markers:
        if marker in text:
            reasons.append(f"Manual review required because code contains: {marker}")

    if reasons:
        return SafetyDecision(mode="manual", reasons=reasons)

    safe_hints = [
        "plot(",
        ".head(",
        ".describe(",
        "plt.",
        "display(",
    ]
    if any(marker in text for marker in safe_hints):
        reasons.append("Looks like an in-memory inspection or plotting task.")
    else:
        reasons.append("No dangerous patterns detected by the basic rules-first safety gate.")
    return SafetyDecision(mode="auto", reasons=reasons)
