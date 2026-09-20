"""Deterministic, numerically faithful explanation generation."""

from __future__ import annotations

from typing import Any


FORBIDDEN_CLAIMS = (
    "caused",
    "will discontinue",
    "trial design increased",
    "enrollment increased",
    "sponsor increased",
    "clinical factor",
    "similar trials",
)


def _facts(result: dict[str, Any], evidence: dict[str, Any]) -> dict[str, str]:
    return {
        "nct_id": str(result["nct_id"]),
        "probability": f"{float(result['predicted_probability']):.6f}",
        "probability_percent": f"{float(result['predicted_probability']):.2%}",
        "year": str(int(evidence["submission_year"])),
        "date": str(evidence["study_first_submitted_date"]),
        "shap": f"{float(result['submission_year_shap_log_odds']):+.6f}",
        "base": f"{float(result['shap_base_log_odds']):+.6f}",
        "decision": f"{float(result['model_decision_log_odds']):+.6f}",
        "dataset": str(evidence["dataset_version"]),
        "model": str(result["model_version"]),
        "source_file": str(evidence["source_file"]),
        "source_field": str(evidence["source_field"]),
    }


def _direction(shap_value: float) -> str:
    if shap_value > 0:
        return "increased"
    if shap_value < 0:
        return "decreased"
    return "did not change"


def generate_explanation(
    result: dict[str, Any],
    evidence: dict[str, Any],
    feedback: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic explanation; feedback changes emphasis, never facts."""
    facts = _facts(result, evidence)
    shap_value = float(result["submission_year_shap_log_odds"])
    direction = _direction(shap_value)
    feedback_text = (feedback or "").strip()
    lowered = feedback_text.lower()

    provenance = (
        f"The verified predictor is submission year {facts['year']}, derived from "
        f"the submission date {facts['date']} in `{facts['source_file']}` field "
        f"`{facts['source_field']}`."
    )
    prediction = (
        f"Model {facts['model']} estimated a discontinuation probability of "
        f"{facts['probability_percent']} (stored value {facts['probability']}) for "
        f"{facts['nct_id']}."
    )
    attribution = (
        f"On the model's log-odds scale, submission year {direction} the score by "
        f"{facts['shap']} relative to the SHAP base value {facts['base']}; their sum "
        f"is the model decision score {facts['decision']}."
    )
    limitation = (
        "This attribution describes the fitted model, not a causal effect or a "
        "percentage-point change. Because submission year is the only predictor, the "
        "baseline does not evaluate trial design, enrollment, sponsor, clinical, or "
        "operational factors and is not clinically validated."
    )
    dataset = (
        f"The record belongs to frozen cohort {facts['dataset']}; current amended "
        "trial fields and the selected trial's actual outcome were not used in this explanation."
    )

    revision_mode = "original"
    if not feedback_text:
        sentences = [prediction, attribution, provenance, dataset, limitation]
    elif any(word in lowered for word in ("short", "concise", "brief")):
        revision_mode = "concise"
        sentences = [prediction, attribution, limitation]
    elif any(word in lowered for word in ("source", "evidence", "provenance", "date")):
        revision_mode = "provenance_first"
        sentences = [provenance, prediction, attribution, dataset, limitation]
    elif any(word in lowered for word in ("uncertain", "uncertainty", "limit", "caution")):
        revision_mode = "limitations_first"
        sentences = [limitation, prediction, attribution, provenance, dataset]
    elif any(word in lowered for word in ("shap", "log-odds", "technical", "calculation")):
        revision_mode = "technical_detail"
        equation = (
            f"The verified additivity check is {facts['base']} + {facts['shap']} = "
            f"{facts['decision']} on the log-odds scale."
        )
        sentences = [prediction, equation, attribution, provenance, limitation]
    else:
        revision_mode = "clarity"
        sentences = [
            prediction,
            provenance,
            attribution,
            "The requested revision changes wording and emphasis only; the stored model and evidence values remain fixed.",
            limitation,
        ]

    text = " ".join(sentences)
    lowered_output = text.lower()
    if any(claim in lowered_output for claim in FORBIDDEN_CLAIMS):
        raise RuntimeError("Deterministic explanation generated a forbidden claim")

    return {
        "text": text,
        "generator": "deterministic_rules_v1",
        "revision_mode": revision_mode,
        "reviewer_feedback_used": bool(feedback_text),
        "numeric_facts": facts,
    }


def generate_failure_explanation(
    metrics: dict[str, Any],
    evidence: dict[str, Any],
    feedback: str | None = None,
) -> dict[str, Any]:
    """Explain the safe no-prediction state without exposing a trial probability."""
    validation = metrics["validation_metrics"]
    facts = {
        "nct_id": str(evidence["nct_id"]),
        "submission_date": str(evidence["study_first_submitted_date"]),
        "submission_year": str(evidence["submission_year"]),
        "dataset_version": str(evidence["dataset_version"]),
        "model_version": str(metrics["model_version"]),
        "validation_auprc": f"{float(validation['auprc']):.6f}",
        "validation_prevalence": f"{float(validation['prevalence_no_skill_auprc']):.6f}",
        "validation_auroc": f"{float(validation['auroc']):.6f}",
    }
    feedback_text = (feedback or "").strip()
    lowered = feedback_text.lower()

    decision = (
        f"No trial-level discontinuation probability is presented for {facts['nct_id']} "
        f"because model {facts['model_version']} failed its basic validation release checks."
    )
    performance = (
        f"Validation AUPRC was {facts['validation_auprc']}, below the validation "
        f"prevalence baseline of {facts['validation_prevalence']}, and validation AUROC "
        f"was {facts['validation_auroc']}, below random ranking performance of 0.5."
    )
    provenance = (
        f"The exact frozen record for {facts['nct_id']} verifies submission date "
        f"{facts['submission_date']} and submission year {facts['submission_year']} in "
        f"cohort {facts['dataset_version']}."
    )
    limitation = (
        "Submission year alone did not provide adequate out-of-time discrimination. "
        "The system therefore blocks the probability, trial-level SHAP display, and "
        "risk explanation rather than presenting an unsupported result."
    )

    revision_mode = "original_failure_notice"
    if not feedback_text:
        sentences = [decision, performance, provenance, limitation]
    elif any(word in lowered for word in ("short", "concise", "brief")):
        revision_mode = "concise_failure_notice"
        sentences = [decision, performance, limitation]
    elif any(word in lowered for word in ("source", "evidence", "provenance", "date")):
        revision_mode = "provenance_first_failure_notice"
        sentences = [provenance, decision, performance, limitation]
    elif any(word in lowered for word in ("metric", "auprc", "auroc", "performance")):
        revision_mode = "metrics_first_failure_notice"
        sentences = [performance, decision, provenance, limitation]
    else:
        revision_mode = "clarified_failure_notice"
        sentences = [decision, limitation, performance, provenance]

    text = " ".join(sentences)
    if "probability is presented" in text.lower() and "no trial-level" not in text.lower():
        raise RuntimeError("Failure explanation implied that a probability was released")
    return {
        "text": text,
        "generator": "deterministic_failure_rules_v1",
        "revision_mode": revision_mode,
        "reviewer_feedback_used": bool(feedback_text),
        "numeric_facts": facts,
    }
