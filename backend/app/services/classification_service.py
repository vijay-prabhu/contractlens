"""Clause classification service using GPT-4o-mini with structured outputs."""
import asyncio
import logging
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import sanitize_for_llm, detect_anomalies
from app.core.clause_taxonomy import (
    get_valid_type_keys,
    get_risk_weights,
    build_clause_types_prompt_section,
)
from app.models.clause import RiskLevel

logger = logging.getLogger(__name__)

settings = get_settings()

# Pinned model version for reproducible classifications (see ADR-009)
CLASSIFICATION_MODEL = "gpt-4o-mini-2024-07-18"

# Risk weights loaded from config/clause_types.yaml (ADR-006)
CLAUSE_TYPE_RISK_WEIGHTS = get_risk_weights()

# Build structured output schema dynamically from taxonomy
_valid_types = get_valid_type_keys()
ClauseTypeEnum = Enum("ClauseTypeEnum", {t.upper(): t for t in _valid_types})

RISK_LEVELS = Enum("RiskLevelEnum", {"LOW": "low", "MEDIUM": "medium", "HIGH": "high", "CRITICAL": "critical"})


class ClauseClassificationSchema(BaseModel):
    """Structured output schema for clause classification."""
    clause_type: str = Field(description=f"One of: {', '.join(_valid_types)}")
    risk_level: str = Field(description="One of: critical, high, medium, low")
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


# Build classification prompt dynamically from taxonomy (ADR-006)
CLASSIFICATION_SYSTEM_PROMPT = f"""You are a legal contract analyst AI specializing in clause classification and risk assessment.

Your task is to analyze contract clauses and provide:
1. Clause type classification
2. Risk level assessment
3. Numerical risk score
4. Brief risk explanation
5. Actionable recommendations (for medium/high/critical risk clauses)

## Clause Types (choose one):
{build_clause_types_prompt_section()}

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
Output: {{"clause_type": "indemnification", "risk_level": "high", "risk_score": 0.75, "risk_explanation": "One-sided indemnification with broad scope covering negligence and breach, no reciprocal obligation from Client.", "confidence": 0.92, "recommendations": ["Add mutual indemnification so both parties share obligations", "Cap indemnification liability at 2x annual contract value"]}}

### Example 2 — Non-Compete (high risk):
Input: "During the term of this Agreement and for a period of twenty-four (24) months following its termination, Provider agrees that it shall not, directly or indirectly, engage in or provide services that are substantially similar to the services provided under this Agreement to any Competing Business within the Territory."
Output: {{"clause_type": "non_compete", "risk_level": "high", "risk_score": 0.7, "risk_explanation": "Broad non-compete with 24-month duration and undefined Territory. Significantly restricts Provider's business opportunities.", "confidence": 0.93, "recommendations": ["Reduce non-compete period to 12 months", "Define Territory and Competing Business narrowly"]}}

### Example 3 — Data Protection (medium risk):
Input: "Both parties shall comply with all applicable data protection and privacy laws including GDPR and CCPA. Provider shall implement appropriate technical and organizational measures to protect personal data against unauthorized access."
Output: {{"clause_type": "data_protection", "risk_level": "medium", "risk_score": 0.55, "risk_explanation": "Standard data protection clause with compliance obligations. Liability for breaches limited by another section.", "confidence": 0.90, "recommendations": ["Add specific breach notification timelines", "Clarify data processing roles (controller vs processor)"]}}

### Example 4 — Notice (low risk):
Input: "All notices under this Agreement shall be in writing and shall be deemed given when delivered personally, sent by confirmed email, or sent by certified mail, return receipt requested, to the addresses set forth on the signature page."
Output: {{"clause_type": "notice", "risk_level": "low", "risk_score": 0.1, "risk_explanation": "Standard notice provision with multiple delivery methods. No unusual requirements.", "confidence": 0.97, "recommendations": []}}"""


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
    clause_type = parsed.clause_type

    # Validate against taxonomy — log unknown types (ADR-006)
    if clause_type not in _valid_types:
        logger.warning(
            f"LLM returned unknown clause type '{clause_type}', falling back to 'other'. "
            f"Consider adding this type to config/clause_types.yaml."
        )
        clause_type = "other"

    # Validate risk level
    valid_levels = [rl.value for rl in RiskLevel]
    risk_level = parsed.risk_level if parsed.risk_level in valid_levels else "low"

    type_weight = CLAUSE_TYPE_RISK_WEIGHTS.get(clause_type, 0.3)
    adjusted_score = (parsed.risk_score * 0.7) + (type_weight * 0.3)

    recommendations = parsed.recommendations[:3] if parsed.recommendations else []

    return ClassificationResult(
        clause_type=clause_type,
        risk_level=risk_level,
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
