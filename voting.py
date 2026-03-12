import json
import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class StructuredResponse:
    recommendation: str
    confidence: float
    risk_score: float
    reasoning: str = ""
    risks: str = ""
    benefits: str = ""


AGENT_WEIGHTS = {
    "Chief Information Security Officer": 1.4,
    "Security Engineer": 1.3,
    "Technology Lawyer": 1.1,
    "Chief Financial Officer": 1.1,
    "Devil's Advocate Risk Analyst": 1.0,
    "AI Reasoning Red Team": 1.0,
    "Cybersecurity Red Team": 1.4,
    "Cloud Architect": 1.2,
    "Threat Intelligence Analyst": 1.3,
    "Compliance Officer": 1.2,
    "AI Safety Officer": 1.2,
}


def parse_structured_response(raw: str) -> StructuredResponse:
    data = _extract_json(raw)

    if data:
        return StructuredResponse(
            recommendation=str(data.get("recommendation", "Unknown")),
            confidence=_bound_score(data.get("confidence", 50)),
            risk_score=_bound_score(data.get("risk_score", 50)),
            reasoning=str(data.get("reasoning", "")),
            risks=str(data.get("risks", "")),
            benefits=str(data.get("benefits", "")),
        )

    confidence = _extract_number(raw, r"confidence\s*[:\-]?\s*(\d{1,3})") or 50
    risk_score = _extract_number(raw, r"risk\s*score\s*[:\-]?\s*(\d{1,3})") or 50

    return StructuredResponse(
        recommendation="Unparsed",
        confidence=_bound_score(confidence),
        risk_score=_bound_score(risk_score),
        reasoning=raw,
    )


def aggregate_weighted_scores(responses: Dict[str, StructuredResponse]) -> Dict[str, float]:
    total_weight = 0.0
    confidence_sum = 0.0
    risk_sum = 0.0

    recommendation_weights: Dict[str, float] = {}

    for role, parsed in responses.items():
        weight = AGENT_WEIGHTS.get(role, 1.0)
        total_weight += weight
        confidence_sum += parsed.confidence * weight
        risk_sum += parsed.risk_score * weight

        key = parsed.recommendation.strip().lower() or "unknown"
        recommendation_weights[key] = recommendation_weights.get(key, 0.0) + weight

    if total_weight == 0:
        return {
            "council_confidence": 0,
            "council_risk_score": 0,
            "leading_recommendation_weight": 0,
            "leading_recommendation": "unknown",
        }

    leading_recommendation = max(recommendation_weights, key=recommendation_weights.get) if recommendation_weights else "unknown"

    return {
        "council_confidence": round(confidence_sum / total_weight, 2),
        "council_risk_score": round(risk_sum / total_weight, 2),
        "leading_recommendation_weight": round(recommendation_weights.get(leading_recommendation, 0.0), 2),
        "leading_recommendation": leading_recommendation,
    }


def _extract_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _extract_number(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _bound_score(value) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = 50.0
    return max(0.0, min(100.0, numeric))
