"""Deterministic, noncausal explanations and separate human-review records."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


FORBIDDEN_CLAIMS = (
    "caused discontinuation",
    "will discontinue",
    "should be terminated",
    "clinical recommendation",
    "clinically high risk",
)


def _direction(value: float) -> str:
    if value > 0:
        return "increased"
    if value < 0:
        return "decreased"
    return "did not change"


def generate_explanation(result: dict[str, Any], feedback: str | None = None) -> dict[str, Any]:
    structured = result["top_structured_contributions"][:3]
    structured_text = "; ".join(
        f"{item['feature']}={item['input_value']!s} {_direction(item['log_odds_contribution'])} "
        f"the model log-odds by {item['log_odds_contribution']:+.4f}"
        for item in structured
    ) or "No nonzero structured contribution was available"
    text_contribution = float(result["criteria_text_contribution"])
    threshold_phrase = (
        "at or above" if result["threshold_position"] == "above_or_equal" else "below"
    )
    base = (
        f"Frozen model {result['model_version']} produced an experimental discontinuation "
        f"score of {result['probability']:.2%} for {result['nct_id']}. The score is "
        f"{threshold_phrase} the development-derived research threshold of "
        f"{result['threshold']:.4f}. This threshold comparison is not a treatment, "
        "clinical, or trial-management recommendation."
    )
    contributions = (
        f"The largest structured terms were: {structured_text}. Eligibility-criteria "
        f"text contributed {text_contribution:+.4f} to the model log-odds after TF-IDF "
        "aggregation. These values describe the fitted model and do not establish causation."
    )
    integrity = (
        f"The additive check reconstructed log-odds {result['reconstructed_log_odds']:+.6f} "
        f"with absolute error {result['additivity_error']:.2e}. The input artifact had "
        f"{len(result['input_missing_fields'])} missing model fields for this record."
    )
    limitation = (
        "The structured and eligibility fields are frozen current-record inputs and are not "
        "claimed to be exact historical registration snapshots. Experimental — not validated "
        "for clinical decision-making."
    )

    feedback_text = (feedback or "").strip()
    lowered = feedback_text.casefold()
    mode = "original"
    sentences = [base, contributions, integrity, limitation]
    if feedback_text:
        if any(word in lowered for word in ("short", "brief", "concise")):
            mode = "concise"
            sentences = [base, contributions, limitation]
        elif any(word in lowered for word in ("limit", "caution", "uncertain")):
            mode = "limitations_first"
            sentences = [limitation, base, contributions, integrity]
        elif any(word in lowered for word in ("technical", "log-odds", "calculation")):
            mode = "technical_first"
            sentences = [integrity, base, contributions, limitation]
        else:
            mode = "clarified"
            sentences.append(
                "Reviewer feedback changed wording only; the frozen score, threshold, and contributions were unchanged."
            )
    text = " ".join(sentences)
    if any(claim in text.casefold() for claim in FORBIDDEN_CLAIMS):
        raise RuntimeError("Explanation generated a forbidden claim")
    return {
        "text": text,
        "generator": "deterministic_lr_contributions_v1",
        "revision_mode": mode,
        "numeric_facts": {
            "probability": result["probability"],
            "threshold": result["threshold"],
            "decision_log_odds": result["decision_log_odds"],
            "reconstructed_log_odds": result["reconstructed_log_odds"],
            "additivity_error": result["additivity_error"],
        },
    }


def make_review_record(
    nct_id: str,
    action: str,
    reviewer_note: str,
    explanation: dict[str, Any],
) -> dict[str, Any]:
    if action not in {"accept", "reject", "request_revision"}:
        raise ValueError(f"Unsupported review action: {action}")
    note = reviewer_note.strip()
    if action in {"reject", "request_revision"} and not note:
        raise ValueError("A reviewer note is required for rejection or revision")
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nct_id": nct_id,
        "action": action,
        "reviewer_note": note,
        "review_is_separate_from_prediction": True,
        "explanation_sha256": hashlib.sha256(explanation["text"].encode()).hexdigest(),
        "generator": explanation["generator"],
        "revision_mode": explanation["revision_mode"],
        "numeric_facts": explanation["numeric_facts"],
    }
