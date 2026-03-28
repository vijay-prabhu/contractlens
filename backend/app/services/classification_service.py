"""Clause classification service using GPT-4o-mini with structured outputs."""
import asyncio
import logging
from typing import List, Literal, Optional
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import sanitize_for_llm, detect_anomalies
from app.models.clause import ClauseType, RiskLevel

logger = logging.getLogger(__name__)

settings = get_settings()

# Pinned model version for reproducible classifications (see ADR-009)
CLASSIFICATION_MODEL = "gpt-4o-mini-2024-07-18"

# Valid values for structured output constraints
CLAUSE_TYPES = Literal[
    "indemnification", "limitation_of_liability", "termination",
    "confidentiality", "payment_terms", "intellectual_property",
    "governing_law", "force_majeure", "warranty", "dispute_resolution",
    "assignment", "notice", "amendment", "entire_agreement", "other",
]

RISK_LEVELS = Literal["critical", "high", "medium", "low"]


class ClauseClassificationSchema(BaseModel):
    """Structured output schema for clause classification."""
    clause_type: CLAUSE_TYPES
    risk_level: RISK_LEVELS
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommendations: List[str] = Field(default_factory=list)


@dataclass
class ClassificationResult:
    """Result of clause classification."""
    clause_type: str
    risk_level: str
    risk_score: float
    risk_explanation: str
    confidence: float
    recommendations: List[str]
    classification_failed: bool = False


# Risk weights by clause type — higher weight = inherently riskier clause type
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
- Be concise but specific

## Examples:

### Example 1 — Indemnification (high risk):
Input: "Provider shall indemnify, defend, and hold harmless Client and its officers, directors, employees, and agents from and against any and all claims, damages, losses, costs, and expenses (including reasonable attorneys' fees) arising out of or relating to Provider's breach of this Agreement or Provider's negligence or willful misconduct."
Output: {"clause_type": "indemnification", "risk_level": "high", "risk_score": 0.75, "risk_explanation": "One-sided indemnification with broad scope covering negligence and breach, no reciprocal obligation from Client.", "confidence": 0.92, "recommendations": ["Add mutual indemnification so both parties share obligations", "Cap indemnification liability at 2x annual contract value"]}

### Example 2 — Limitation of Liability (medium risk):
Input: "IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY UNDER THIS AGREEMENT EXCEED THE TOTAL FEES PAID BY CLIENT IN THE TWELVE (12) MONTH PERIOD IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO THE CLAIM. NEITHER PARTY SHALL BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES."
Output: {"clause_type": "limitation_of_liability", "risk_level": "medium", "risk_score": 0.5, "risk_explanation": "Mutual liability cap at 12 months of fees is reasonable. Consequential damages exclusion is standard but may limit recovery for significant data breaches.", "confidence": 0.95, "recommendations": ["Carve out data breach and IP infringement from consequential damages exclusion"]}

### Example 3 — Notice (low risk):
Input: "All notices under this Agreement shall be in writing and shall be deemed given when delivered personally, sent by confirmed email, or sent by certified mail, return receipt requested, to the addresses set forth on the signature page."
Output: {"clause_type": "notice", "risk_level": "low", "risk_score": 0.1, "risk_explanation": "Standard notice provision with multiple delivery methods. No unusual requirements.", "confidence": 0.97, "recommendations": []}

### Example 4 — Termination (high risk):
Input: "Client may terminate this Agreement at any time for any reason upon thirty (30) days' written notice. Provider may only terminate this Agreement in the event of Client's material breach that remains uncured for sixty (60) days after written notice."
Output: {"clause_type": "termination", "risk_level": "high", "risk_score": 0.7, "risk_explanation": "Asymmetric termination rights — Client can terminate for convenience but Provider requires material breach with 60-day cure period. Significantly favors Client.", "confidence": 0.91, "recommendations": ["Negotiate mutual termination for convenience rights", "Reduce cure period to 30 days for both parties"]}"""


def _make_failed_result(error_msg: str) -> ClassificationResult:
    """Create a ClassificationResult with the failure flag set."""
    return ClassificationResult(
        clause_type=ClauseType.OTHER.value,
        risk_level=RiskLevel.LOW.value,
        risk_score=0.0,
        risk_explanation=f"Classification failed: {error_msg}",
        confidence=0.0,
        recommendations=[],
        classification_failed=True,
    )


def _make_empty_result() -> ClassificationResult:
    """Create a ClassificationResult for empty input."""
    return ClassificationResult(
        clause_type=ClauseType.OTHER.value,
        risk_level=RiskLevel.LOW.value,
        risk_score=0.0,
        risk_explanation="Empty or whitespace-only text",
        confidence=0.0,
        recommendations=[],
        classification_failed=False,
    )


def _apply_risk_weight(parsed: ClauseClassificationSchema) -> ClassificationResult:
    """Convert structured output to ClassificationResult with risk weight blending."""
    type_weight = CLAUSE_TYPE_RISK_WEIGHTS.get(parsed.clause_type, 0.3)
    adjusted_score = (parsed.risk_score * 0.7) + (type_weight * 0.3)

    recommendations = parsed.recommendations[:3] if parsed.recommendations else []

    return ClassificationResult(
        clause_type=parsed.clause_type,
        risk_level=parsed.risk_level,
        risk_score=round(adjusted_score, 3),
        risk_explanation=parsed.risk_explanation,
        confidence=parsed.confidence,
        recommendations=recommendations,
        classification_failed=False,
    )


def _create_openai_clients():
    """Create OpenAI clients — with Langfuse wrapper if configured."""
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            import os
            # Langfuse OpenAI wrapper reads these env vars directly
            os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
            os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
            os.environ["LANGFUSE_HOST"] = settings.langfuse_host

            from langfuse.openai import OpenAI as LangfuseOpenAI
            from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
            logger.info("Langfuse AI observability enabled")
            return (
                LangfuseOpenAI(api_key=settings.openai_api_key),
                LangfuseAsyncOpenAI(api_key=settings.openai_api_key),
            )
        except Exception as e:
            logger.warning(f"Langfuse wrapper init failed, using plain OpenAI: {e}")

    from openai import AsyncOpenAI, OpenAI
    return OpenAI(api_key=settings.openai_api_key), AsyncOpenAI(api_key=settings.openai_api_key)


class ClassificationService:
    """Service for classifying contract clauses using GPT-4o-mini."""

    def __init__(self):
        self.client, self.async_client = _create_openai_clients()
        self.model = CLASSIFICATION_MODEL

    def classify_clause(self, text: str) -> ClassificationResult:
        """Classify a single clause using structured outputs."""
        if not text.strip():
            return _make_empty_result()

        safe_text = sanitize_for_llm(text)

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this contract clause:\n\n{safe_text}"},
                ],
                response_format=ClauseClassificationSchema,
                temperature=0,
            )

            parsed = response.choices[0].message.parsed
            if parsed is None:
                return _make_failed_result("Model returned empty response")

            result = _apply_risk_weight(parsed)
            detect_anomalies(text, result.clause_type, result.risk_level, result.confidence)
            return result

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return _make_failed_result(str(e))

    async def classify_clause_async(self, text: str) -> ClassificationResult:
        """Classify a single clause asynchronously using structured outputs."""
        if not text.strip():
            return _make_empty_result()

        safe_text = sanitize_for_llm(text)

        try:
            response = await self.async_client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this contract clause:\n\n{safe_text}"},
                ],
                response_format=ClauseClassificationSchema,
                temperature=0,
            )

            parsed = response.choices[0].message.parsed
            if parsed is None:
                return _make_failed_result("Model returned empty response")

            result = _apply_risk_weight(parsed)
            detect_anomalies(text, result.clause_type, result.risk_level, result.confidence)
            return result

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return _make_failed_result(str(e))

    async def classify_clauses_batch_async(
        self, texts: List[str], concurrency: int = 10
    ) -> List[ClassificationResult]:
        """Classify multiple clauses concurrently."""
        semaphore = asyncio.Semaphore(concurrency)

        async def classify_with_limit(text: str) -> ClassificationResult:
            async with semaphore:
                return await self.classify_clause_async(text)

        results = await asyncio.gather(
            *[classify_with_limit(text) for text in texts]
        )

        failed = sum(1 for r in results if r.classification_failed)
        if failed > 0:
            logger.warning(f"Classification: {failed}/{len(results)} clauses failed")

        logger.info(f"Classified {len(results)}/{len(texts)} clauses (concurrency={concurrency})")
        return list(results)

    def classify_clauses_batch(
        self, texts: List[str], batch_size: int = 5
    ) -> List[ClassificationResult]:
        """Classify multiple clauses (sync wrapper, kept for backwards compat)."""
        results = []
        for i, text in enumerate(texts):
            result = self.classify_clause(text)
            results.append(result)
            if (i + 1) % 10 == 0:
                logger.info(f"Classified {i + 1}/{len(texts)} clauses")
        return results

    def calculate_document_risk_summary(
        self, classifications: List[ClassificationResult]
    ) -> dict:
        """Calculate overall document risk summary from classified clauses.

        Delegates to risk_scoring.compute_document_risk (ADR-008).
        """
        from app.services.risk_scoring import compute_document_risk

        result = compute_document_risk(classifications)
        return {
            "overall_risk_score": result.overall_risk_score,
            "overall_risk_level": result.overall_risk_level,
            "clause_count": result.clause_count,
            "risk_distribution": result.risk_distribution,
            "high_risk_clauses": result.high_risk_clauses,
            "critical_clauses": result.critical_clauses,
        }
