"""On-demand order explanations through the official OpenAI Python SDK."""

import json
import logging

from django.conf import settings
from openai import OpenAI, OpenAIError

logger = logging.getLogger("orders.ai")


class AIExplanationUnavailable(Exception):
    """Raised when an explanation cannot be safely produced."""


def generate_order_explanation(order):
    if not settings.OPENAI_API_KEY:
        raise AIExplanationUnavailable(
            "AI explanation is currently unavailable. Add OPENAI_API_KEY in Replit Secrets to enable it."
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

    try:
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=18.0,
            max_retries=0,
        )
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            max_output_tokens=220,
            instructions=(
                "Write a concise explanation for a human e-commerce order reviewer. "
                "Use only the facts and detected signals in the supplied JSON. "
                "Explain which observed signals contributed to the score in plain language. "
                "Do not infer missing facts, describe the order as fraud, or recommend an "
                "automatic approve/reject decision. Make clear that a human reviewer decides."
            ),
            input=json.dumps(evidence, ensure_ascii=False),
        )
        explanation = (response.output_text or "").strip()
        if not explanation:
            raise AIExplanationUnavailable(
                "The AI service returned an empty explanation. Please try again."
            )
        return explanation
    except AIExplanationUnavailable:
        raise
    except OpenAIError as exc:
        # Log only the exception class and order ID; never log credentials or API payloads.
        logger.warning(
            "OpenAI explanation request failed for order %s (%s)",
            order.order_number,
            type(exc).__name__,
        )
        raise AIExplanationUnavailable(
            "AI explanation is temporarily unavailable. Please try again shortly."
        ) from None