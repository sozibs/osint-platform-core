"""Propaganda detector: identifies common propaganda techniques in text."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_TECHNIQUES: Dict[str, List[str]] = {
    "appeal_to_fear": [
        "threat", "danger", "crisis", "catastrophe", "devastating",
    ],
    "bandwagon": [
        "everyone knows", "all experts agree", "most people", "everybody",
    ],
    "loaded_language": [
        "radical", "extremist", "corrupt", "evil", "destroy",
    ],
    "false_dilemma": [
        "either", "or else", "you're either with us", "no choice",
    ],
    "scapegoating": [
        "they are responsible", "blame the", "it's their fault",
    ],
}


class PropagandaDetector:
    """Detects propaganda techniques via keyword pattern matching."""

    async def detect(self, text: str) -> Dict[str, Any]:
        """Identify propaganda techniques present in *text*.

        Returns:
            techniques_detected: list of technique names found
            technique_details: matched keywords per technique
            propaganda_score: fraction of techniques triggered (0.0–1.0)
        """
        lower = text.lower()
        techniques_detected: List[str] = []
        technique_details: Dict[str, List[str]] = {}

        for technique, keywords in _TECHNIQUES.items():
            matched = [kw for kw in keywords if kw in lower]
            if matched:
                techniques_detected.append(technique)
                technique_details[technique] = matched

        propaganda_score = round(len(techniques_detected) / len(_TECHNIQUES), 4)

        return {
            "techniques_detected": techniques_detected,
            "technique_details": technique_details,
            "propaganda_score": propaganda_score,
        }
