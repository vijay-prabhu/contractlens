"""Clause classification service using GPT-4o-mini."""
import json
import logging
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from openai import OpenAI

from app.core.config import get_settings
from app.models.clause import ClauseType, RiskLevel

logger = logging.getLogger(__name__)

settings = get_settings()

# Use GPT-4o-mini for cost-effective classification
CLASSIFICATION_MODEL = "gpt-4o-mini"


@dataclass
class ClassificationResult:
    """Result of clause classification."""
    clause_type: str
    risk_level: str
    risk_score: float  # 0.0 to 1.0
    risk_explanation: str
    confidence: float  # 0.0 to 1.0
    recommendations: List[str]  # List of actionable recommendations


# Risk weights by clause type - higher weight = inherently riskier clause type
CLAUSE_TYPE_RISK_WEIGHTS = {
    ClauseType.INDEMNIFICATION.value: 0.8,
    ClauseType.LIMITATION_OF_LIABILITY.value: 0.85,
    ClauseType.TERMINATION.value: 0.6,
    ClauseType.CONFIDENTIALITY.value: 0.5,
    ClauseType.INTELLECTUAL_PROPERTY.value: 0.7,
    ClauseType.WARRANTY.value: 0.65,
    ClauseType.DISPUTE_RESOLUTION.value: 0.55,
    ClauseType.FORCE_MAJEURE.value: 0.5,
    ClauseType.PAYMENT_TERMS.value: 0.45,
    ClauseType.GOVERNING_LAW.value: 0.3,
    ClauseType.ASSIGNMENT.value: 0.4,
    ClauseType.NOTICE.value: 0.2,
    ClauseType.AMENDMENT.value: 0.35,
    ClauseType.ENTIRE_AGREEMENT.value: 0.25,
    ClauseType.OTHER.value: 0.3,
}


CLASSIFICATION_SYSTEM_PROMPT = """You are a legal contract analyst AI specializing in clause classification and risk assessment.

Your task is to analyze contract clauses and provide:
1. Clause type classification
2. Risk level assessment
3. Numerical risk score
4. Brief risk explanation
5. Actionable recommendations (for medium/high/critical risk clauses)

## Clause Types (choose one):
- indemnification: Clauses about protecting parties from losses, damages, or liabilities
- limitation_of_liability: Clauses limiting damages or liability exposure
- termination: Clauses about contract termination conditions and procedures
- confidentiality: Clauses about protecting confidential information
- payment_terms: Clauses about payment schedules, amounts, penalties
- intellectual_property: Clauses about IP ownership, licensing, rights
- governing_law: Clauses specifying applicable law and jurisdiction
- force_majeure: Clauses about unforeseeable circumstances
- warranty: Clauses about guarantees, representations, disclaimers
- dispute_resolution: Clauses about resolving disputes (arbitration, mediation)
- assignment: Clauses about transferring rights or obligations
- notice: Clauses about notification requirements
- amendment: Clauses about modifying the agreement
- entire_agreement: Integration clauses, superseding prior agreements
- other: Does not fit above categories

## Risk Levels:
- critical: Severe financial/legal exposure, immediate attention needed
- high: Significant risk that should be negotiated
- medium: Moderate risk, review recommended
- low: Standard clause with minimal risk

## Risk Assessment Factors:
Consider these when assessing risk:
- One-sided obligations (favoring one party significantly)
- Unlimited liability exposure
- Broad indemnification requirements
- Waiver of important rights
- Automatic renewal without notice
- Difficult termination conditions
- Unreasonable timeframes
- Missing important protections
- Ambiguous or vague language

## Recommendations Guidelines:
- For low risk: provide empty array []
- For medium/high/critical risk: provide 1-3 specific, actionable recommendations
- Focus on what can be negotiated or changed
- Be concise but specific (e.g., "Add a liability cap of 2x annual fees" not "Consider limiting liability")

Respond ONLY with valid JSON in this exact format:
{
    "clause_type": "<type>",
    "risk_level": "<level>",
    "risk_score": <0.0-1.0>,
    "risk_explanation": "<1-2 sentence explanation>",
    "confidence": <0.0-1.0>,
    "recommendations": ["<recommendation 1>", "<recommendation 2>"]
}"""


class ClassificationService:
    """Service for classifying contract clauses using GPT-4o-mini."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = CLASSIFICATION_MODEL

    def classify_clause(self, text: str) -> ClassificationResult:
        """Classify a single clause.

        Args:
            text: The clause text to classify

        Returns:
            ClassificationResult with type, risk level, score, and explanation
        """
        if not text.strip():
            return ClassificationResult(
                clause_type=ClauseType.OTHER.value,
                risk_level=RiskLevel.LOW.value,
                risk_score=0.0,
                risk_explanation="Empty or whitespace-only text",
                confidence=0.0,
                recommendations=[],
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this contract clause:\n\n{text}"},
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=300,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            result = self._parse_classification_response(result_text)

            # Validate and normalize values
            result = self._validate_result(result, text)

            return result

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # Return safe defaults on error
            return ClassificationResult(
                clause_type=ClauseType.OTHER.value,
                risk_level=RiskLevel.LOW.value,
                risk_score=0.0,
                risk_explanation=f"Classification error: {str(e)}",
                confidence=0.0,
                recommendations=[],
            )

    def classify_clauses_batch(
        self, texts: List[str], batch_size: int = 5
    ) -> List[ClassificationResult]:
        """Classify multiple clauses.

        Args:
            texts: List of clause texts to classify
            batch_size: Number of clauses to classify in parallel (not implemented yet)

        Returns:
            List of ClassificationResults in same order as input
        """
        results = []
        for i, text in enumerate(texts):
            try:
                result = self.classify_clause(text)
                results.append(result)
                if (i + 1) % 10 == 0:
                    logger.info(f"Classified {i + 1}/{len(texts)} clauses")
            except Exception as e:
                logger.error(f"Failed to classify clause {i}: {e}")
                results.append(ClassificationResult(
                    clause_type=ClauseType.OTHER.value,
                    risk_level=RiskLevel.LOW.value,
                    risk_score=0.0,
                    risk_explanation=f"Classification error: {str(e)}",
                    confidence=0.0,
                    recommendations=[],
                ))

        return results

    def _parse_classification_response(self, response_text: str) -> dict:
        """Parse the JSON response from GPT-4o-mini."""
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        return json.loads(response_text.strip())

    def _validate_result(self, parsed: dict, original_text: str) -> ClassificationResult:
        """Validate and normalize classification result."""
        # Validate clause_type
        valid_types = [t.value for t in ClauseType]
        clause_type = parsed.get("clause_type", "other").lower()
        if clause_type not in valid_types:
            clause_type = ClauseType.OTHER.value

        # Validate risk_level
        valid_levels = [r.value for r in RiskLevel]
        risk_level = parsed.get("risk_level", "low").lower()
        if risk_level not in valid_levels:
            risk_level = RiskLevel.LOW.value

        # Validate risk_score (0.0 to 1.0)
        risk_score = parsed.get("risk_score", 0.0)
        try:
            risk_score = float(risk_score)
            risk_score = max(0.0, min(1.0, risk_score))
        except (ValueError, TypeError):
            risk_score = 0.0

        # Apply clause type risk weight to score
        type_weight = CLAUSE_TYPE_RISK_WEIGHTS.get(clause_type, 0.3)
        # Blend LLM assessment with type-based weight
        adjusted_score = (risk_score * 0.7) + (type_weight * 0.3)

        # Validate confidence
        confidence = parsed.get("confidence", 0.5)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5

        # Get explanation
        risk_explanation = parsed.get("risk_explanation", "No explanation provided")
        if not isinstance(risk_explanation, str):
            risk_explanation = str(risk_explanation)

        # Get recommendations
        recommendations = parsed.get("recommendations", [])
        if not isinstance(recommendations, list):
            recommendations = []
        # Ensure all items are strings and limit to 3
        recommendations = [str(r) for r in recommendations if r][:3]

        return ClassificationResult(
            clause_type=clause_type,
            risk_level=risk_level,
            risk_score=round(adjusted_score, 3),
            risk_explanation=risk_explanation,
            confidence=confidence,
            recommendations=recommendations,
        )

    def calculate_document_risk_summary(
        self, classifications: List[ClassificationResult]
    ) -> dict:
        """Calculate overall document risk summary from classified clauses.

        Args:
            classifications: List of classification results for all clauses

        Returns:
            Dictionary with risk summary statistics
        """
        if not classifications:
            return {
                "overall_risk_score": 0.0,
                "overall_risk_level": RiskLevel.LOW.value,
                "clause_count": 0,
                "risk_distribution": {},
                "high_risk_clauses": 0,
                "critical_clauses": 0,
            }

        # Count risk levels
        risk_counts = {level.value: 0 for level in RiskLevel}
        for c in classifications:
            risk_counts[c.risk_level] += 1

        # Calculate overall risk score (weighted average)
        total_score = sum(c.risk_score for c in classifications)
        avg_score = total_score / len(classifications)

        # Determine overall risk level based on critical/high risk clause counts
        critical_count = risk_counts[RiskLevel.CRITICAL.value]
        high_count = risk_counts[RiskLevel.HIGH.value]

        if critical_count >= 1:
            overall_level = RiskLevel.CRITICAL.value
        elif high_count >= 3 or (high_count >= 1 and avg_score > 0.6):
            overall_level = RiskLevel.HIGH.value
        elif avg_score > 0.4:
            overall_level = RiskLevel.MEDIUM.value
        else:
            overall_level = RiskLevel.LOW.value

        return {
            "overall_risk_score": round(avg_score, 3),
            "overall_risk_level": overall_level,
            "clause_count": len(classifications),
            "risk_distribution": risk_counts,
            "high_risk_clauses": high_count,
            "critical_clauses": critical_count,
        }
