"""On-demand order explanations through the official Google GenAI Python SDK."""

import json
import logging
import os
import time

from django.conf import settings

try:
    from google import genai
    from google.genai import errors as genai_errors
except Exception:  # pragma: no cover - optional dependency
    genai = None
    genai_errors = None

logger = logging.getLogger("orders.ai")


class AIExplanationUnavailable(Exception):
    """Raised when an explanation cannot be safely produced."""


def _log_gemini_error(exc: Exception, order_number: str) -> None:
    """Log useful Gemini error details without secrets."""
    error_code = getattr(exc, "code", None)
    http_status = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)
    logger.warning(
        "Gemini explanation request failed for order %s (type=%s code=%s status=%s request_id=%s)",
        order_number,
        type(exc).__name__,
        error_code,
        http_status,
        request_id,
    )


def _is_quota_error(exc: Exception) -> bool:
    """Check if the error indicates exhausted quota/billing."""
    error_code = str(getattr(exc, "code", "")).lower()
    return any(
        keyword in error_code
        for keyword in (
            "quota",
            "billing",
            "insufficient",
            "exhausted",
            "limit_exceeded",
        )
    )


def _call_gemini_with_retry(client, prompt: str, order_number: str) -> str:
    """Call Gemini with a small bounded retry for transient rate limits."""
    max_attempts = 3
    base_delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
            )
            explanation = (response.text or "").strip()
            if not explanation:
                raise AIExplanationUnavailable(
                    "The AI service returned an empty explanation. Please try again."
                )
            return explanation
        except Exception as exc:
            _log_gemini_error(exc, order_number)
            if _is_quota_error(exc):
                raise AIExplanationUnavailable(
                    "AI explanation is currently unavailable because the API quota is exhausted."
                ) from None
            if attempt == max_attempts:
                raise AIExplanationUnavailable(
                    "AI explanation is temporarily unavailable. Please try again shortly."
                ) from None
            time.sleep(base_delay * attempt)


def generate_order_explanation(order):
    if not getattr(settings, "GEMINI_API_KEY", ""):
        raise AIExplanationUnavailable(
            "AI explanation is currently unavailable because GEMINI_API_KEY is not configured."
        )

    if genai is None:
        raise AIExplanationUnavailable(
            "AI explanation is currently unavailable because the Gemini SDK is not installed."
        )

    evidence = {
        "order_id": order.order_number,
        "amount": str(order.amount),
        "currency": "USD",
        "ordered_at": order.ordered_at.isoformat(),
        "payment_method": order.payment_method,
        "payment_attempts": order.payment_attempts,
        "risk_score": order.risk_score,
        "risk_level": order.get_risk_level_display(),
        "detected_signals": [
            {
                "name": signal.label,
                "observed_evidence": signal.description,
                "score_contribution": signal.points,
            }
            for signal in order.signals.all()
        ],
        "products": [
            {
                "name": item.product_name,
                "category": item.category,
                "quantity": item.quantity,
            }
            for item in order.items.all()
        ],
    }

    prompt = (
        "Write a concise explanation for a human e-commerce order reviewer. "
        "Use only the facts and detected signals in the supplied JSON. "
        "Explain which observed signals contributed to the score in plain language. "
        "Do not infer missing facts, describe the order as fraud, or recommend an "
        "automatic approve/reject decision. Make clear that a human reviewer decides.\n\n"
        f"Order evidence (JSON):\n{json.dumps(evidence, ensure_ascii=False)}"
    )

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return _call_gemini_with_retry(client, prompt, order.order_number)
    except AIExplanationUnavailable:
        raise
    except Exception as exc:
        _log_gemini_error(exc, order.order_number)
        if _is_quota_error(exc):
            raise AIExplanationUnavailable(
                "AI explanation is currently unavailable because the API quota is exhausted."
            ) from None
        raise AIExplanationUnavailable(
            "AI explanation is temporarily unavailable. Please try again shortly."
        ) from None