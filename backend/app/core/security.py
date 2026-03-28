"""AI security mitigations — OWASP LLM Top 10 (ADR-014).

Input sanitization: strips known prompt injection patterns before LLM calls.
Output anomaly detection: flags suspicious classifications.
Rate limiting: per-user throttling on uploads and processing.
"""
import logging
import re
from typing import List

logger = logging.getLogger(__name__)

# Known prompt injection patterns — catches common attacks, not exhaustive
INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instructions"),
    re.compile(r"(?i)you\s+are\s+now\s+a"),
    re.compile(r"(?i)system\s*:\s*"),
    re.compile(r"(?i)respond\s+with\s+only"),
    re.compile(r"(?i)classify\s+(this|everything)\s+as"),
    re.compile(r"(?i)override\s+(the\s+)?classification"),
    re.compile(r"(?i)disregard\s+(all\s+)?(prior|previous|above)"),
    re.compile(r"(?i)new\s+instructions?\s*:"),
    re.compile(r"(?i)forget\s+(everything|all|prior)"),
    re.compile(r"(?i)output\s+only\s+(json|the\s+following)"),
]

# Keywords that indicate specific clause types — used for anomaly detection
INDEMNIFICATION_KEYWORDS = ["indemnify", "hold harmless", "defend and indemnify", "indemnification"]
LIABILITY_KEYWORDS = ["limitation of liability", "aggregate liability", "liable", "damages"]
TERMINATION_KEYWORDS = ["terminate", "termination", "expiration"]
CONFIDENTIALITY_KEYWORDS = ["confidential", "non-disclosure", "proprietary information"]


def sanitize_for_llm(text: str) -> str:
    """Remove known prompt injection patterns from document text.

    This is defense-in-depth — not foolproof against sophisticated attacks,
    but catches the most common injection vectors.

    Args:
        text: Raw document text

    Returns:
        Sanitized text with injection patterns redacted
    """
    redacted_count = 0
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            text = pattern.sub("[REDACTED]", text)
            redacted_count += 1

    if redacted_count > 0:
        logger.warning(f"Sanitized {redacted_count} potential prompt injection pattern(s)")

    return text


def detect_anomalies(clause_text: str, clause_type: str, risk_level: str, confidence: float) -> List[str]:
    """Check if a classification result is suspicious.

    Looks for mismatches between text content and classification. Anomalies
    are logged and flagged, not blocked — to avoid false positive rejections.

    Args:
        clause_text: The original clause text
        clause_type: Classified clause type
        risk_level: Classified risk level
        confidence: Classification confidence score

    Returns:
        List of warning strings (empty if no anomalies)
    """
    warnings = []
    text_lower = clause_text.lower()

    # Indemnification keywords but not classified as indemnification
    if any(kw in text_lower for kw in INDEMNIFICATION_KEYWORDS):
        if clause_type != "indemnification" and risk_level == "low":
            warnings.append(
                "Text contains indemnification language but classified as "
                f"{clause_type}/{risk_level}"
            )

    # Liability keywords but classified as low risk
    if any(kw in text_lower for kw in LIABILITY_KEYWORDS):
        if clause_type not in ("limitation_of_liability", "indemnification") and risk_level == "low":
            warnings.append(
                "Text contains liability language but classified as "
                f"{clause_type}/{risk_level}"
            )

    # Termination keywords but not classified as termination
    if "terminat" in text_lower and clause_type != "termination" and clause_type != "other":
        if risk_level == "low" and len(clause_text) > 200:
            warnings.append(
                "Text contains termination language but classified as "
                f"{clause_type}/{risk_level}"
            )

    # Low confidence on substantial text
    if len(clause_text) > 200 and confidence < 0.3:
        warnings.append(
            f"Low confidence ({confidence:.0%}) on substantial text — "
            "possible injection or parsing issue"
        )

    # Suspiciously short text classified as high/critical
    if len(clause_text) < 50 and risk_level in ("high", "critical"):
        warnings.append(
            f"Very short text ({len(clause_text)} chars) classified as {risk_level}"
        )

    if warnings:
        for w in warnings:
            logger.warning(f"[ANOMALY] {w}")

    return warnings


# Rate limiting helpers (requires Redis)
RATE_LIMITS = {
    "upload": 20,       # documents per hour
    "process": 100,     # classification calls per hour
}


async def check_rate_limit(redis_client, user_id: str, action: str) -> bool:
    """Check if user is within rate limits.

    Args:
        redis_client: Redis client instance
        user_id: User UUID string
        action: Action type ('upload' or 'process')

    Returns:
        True if within limits, False if exceeded
    """
    if redis_client is None:
        return True  # No Redis = no rate limiting

    limit = RATE_LIMITS.get(action, 100)
    key = f"rate_limit:{action}:{user_id}"

    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, 3600)  # 1 hour window
        return current <= limit
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True  # Fail open — don't block users if Redis is down
