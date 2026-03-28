"""Document-level risk scoring — single source of truth (ADR-008).

Replaces simple averaging with a CVSS-inspired formula:
  document_risk = max_clause * 0.4 + top_n_weighted_avg * 0.35 + concentration * 0.25

This ensures a single critical clause drives the score instead of being
diluted by many low-risk clauses.
"""
from dataclasses import dataclass
from typing import List

from app.core.constants import RISK_MEDIUM_THRESHOLD
from app.services.classification_service import CLAUSE_TYPE_RISK_WEIGHTS, ClassificationResult
from app.models.clause import RiskLevel


TOP_N_CLAUSES = 5
CONCENTRATION_SCALE = 1.2
RELATIVE_TREND_THRESHOLD = 0.05  # 5% relative change

RISK_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class DocumentRiskScore:
    """Computed document-level risk."""
    overall_risk_score: float
    overall_risk_level: str
    clause_count: int
    risk_distribution: dict
    high_risk_clauses: int
    critical_clauses: int


@dataclass
class ComparisonRiskSummary:
    """Risk summary for version comparison."""
    old_overall_score: float
    new_overall_score: float
    risk_trend: str
    critical_added: int
    critical_removed: int
    high_risk_added: int
    high_risk_removed: int
    risk_escalations: int
    risk_deescalations: int


def compute_document_risk(classifications: List[ClassificationResult]) -> DocumentRiskScore:
    """Compute document-level risk from clause classifications.

    Formula: max_clause * 0.4 + top_n_weighted_avg * 0.35 + concentration * 0.25
    """
    if not classifications:
        return DocumentRiskScore(
            overall_risk_score=0.0,
            overall_risk_level=RiskLevel.LOW.value,
            clause_count=0,
            risk_distribution={},
            high_risk_clauses=0,
            critical_clauses=0,
        )

    scores = [c.risk_score for c in classifications]
    risk_counts = {level.value: 0 for level in RiskLevel}
    for c in classifications:
        risk_counts[c.risk_level] += 1

    critical_count = risk_counts[RiskLevel.CRITICAL.value]
    high_count = risk_counts[RiskLevel.HIGH.value]

    # Component 1: max clause score (40%)
    max_score = max(scores)

    # Component 2: top-N weighted average (35%)
    sorted_clauses = sorted(classifications, key=lambda c: c.risk_score, reverse=True)
    top_n = sorted_clauses[:TOP_N_CLAUSES]

    weighted_scores = []
    weight_sum = 0.0
    for c in top_n:
        w = CLAUSE_TYPE_RISK_WEIGHTS.get(c.clause_type, 0.3)
        weighted_scores.append(c.risk_score * w)
        weight_sum += w

    top_n_avg = sum(weighted_scores) / weight_sum if weight_sum > 0 else 0.0

    # Component 3: concentration penalty (25%)
    medium_plus = sum(1 for s in scores if s > RISK_MEDIUM_THRESHOLD)
    concentration = min((medium_plus / len(scores)) * CONCENTRATION_SCALE, 1.0)

    # Combined score
    overall_score = (max_score * 0.4) + (top_n_avg * 0.35) + (concentration * 0.25)
    overall_score = round(min(overall_score, 1.0), 3)

    # Risk level from distribution
    if critical_count >= 1:
        overall_level = RiskLevel.CRITICAL.value
    elif high_count >= 3 or (high_count >= 1 and overall_score > 0.55):
        overall_level = RiskLevel.HIGH.value
    elif risk_counts[RiskLevel.MEDIUM.value] >= len(classifications) / 2 or overall_score > 0.4:
        overall_level = RiskLevel.MEDIUM.value
    else:
        overall_level = RiskLevel.LOW.value

    return DocumentRiskScore(
        overall_risk_score=overall_score,
        overall_risk_level=overall_level,
        clause_count=len(classifications),
        risk_distribution=risk_counts,
        high_risk_clauses=high_count,
        critical_clauses=critical_count,
    )


def compute_comparison_risk(
    old_score: float,
    new_score: float,
    changes: list,
) -> ComparisonRiskSummary:
    """Compute risk summary for version comparison with relative trend detection."""
    # Count added/removed by risk level
    critical_added = sum(
        1 for c in changes
        if c.change_type.value == "added" and c.new_risk_level == "critical"
    )
    critical_removed = sum(
        1 for c in changes
        if c.change_type.value == "removed" and c.old_risk_level == "critical"
    )
    high_added = sum(
        1 for c in changes
        if c.change_type.value == "added" and c.new_risk_level == "high"
    )
    high_removed = sum(
        1 for c in changes
        if c.change_type.value == "removed" and c.old_risk_level == "high"
    )

    # Track risk level transitions on modified clauses
    risk_escalations = 0
    risk_deescalations = 0
    for c in changes:
        if c.change_type.value == "modified" and c.old_risk_level and c.new_risk_level:
            old_order = RISK_LEVEL_ORDER.get(c.old_risk_level, 0)
            new_order = RISK_LEVEL_ORDER.get(c.new_risk_level, 0)
            if new_order > old_order:
                risk_escalations += 1
            elif new_order < old_order:
                risk_deescalations += 1

    # Relative trend detection (5% relative change)
    if old_score > 0:
        relative_change = (new_score - old_score) / old_score
    else:
        relative_change = 0.0 if new_score == 0 else 1.0

    if relative_change > RELATIVE_TREND_THRESHOLD:
        trend = "increased"
    elif relative_change < -RELATIVE_TREND_THRESHOLD:
        trend = "decreased"
    else:
        trend = "unchanged"

    return ComparisonRiskSummary(
        old_overall_score=round(old_score, 3),
        new_overall_score=round(new_score, 3),
        risk_trend=trend,
        critical_added=critical_added,
        critical_removed=critical_removed,
        high_risk_added=high_added,
        high_risk_removed=high_removed,
        risk_escalations=risk_escalations,
        risk_deescalations=risk_deescalations,
    )
