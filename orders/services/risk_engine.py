"""Transparent, deterministic order-risk scoring."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg
from django.utils import timezone

from orders.models import Order, RiskSignal


@dataclass(frozen=True)
class SignalFinding:
    code: str
    label: str
    description: str
    points: int


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    level: str
    signals: tuple[SignalFinding, ...]


def classify_risk(score: int) -> str:
    """Map a bounded risk score to the dashboard's three risk bands."""
    bounded_score = max(0, min(int(score), 100))
    if bounded_score <= 30:
        return Order.RiskLevel.LOW
    if bounded_score <= 60:
        return Order.RiskLevel.MEDIUM
    return Order.RiskLevel.HIGH


def assess_order(order: Order) -> RiskAssessment:
    """Calculate explainable signals using only this order and customer history."""
    history = Order.objects.filter(customer_id=order.customer_id).exclude(pk=order.pk)
    previous_orders = history.filter(ordered_at__lt=order.ordered_at)
    previous_count = previous_orders.count()
    previous_average = previous_orders.aggregate(value=Avg("amount"))["value"]
    findings = []

    if previous_average and order.amount >= previous_average * Decimal("2.5"):
        findings.append(
            SignalFinding(
                "unusually_high_amount",
                "Unusually high order amount",
                "This order is at least 2.5× the customer's average previous order value.",
                25,
            )
        )
    elif previous_average and order.amount >= previous_average * Decimal("1.7"):
        findings.append(
            SignalFinding(
                "history_deviation",
                "Above the customer's usual order value",
                "This order is at least 1.7× the customer's average previous order value.",
                15,
            )
        )

    if previous_count:
        address_seen = previous_orders.filter(
            delivery_address__iexact=order.delivery_address
        ).exists()
        if not address_seen:
            findings.append(
                SignalFinding(
                    "new_delivery_address",
                    "New delivery address",
                    "The delivery address does not match an address in this customer's previous orders.",
                    20,
                )
            )

    recent_start = order.ordered_at - timedelta(hours=24)
    recent_count = history.filter(
        ordered_at__gte=recent_start, ordered_at__lt=order.ordered_at
    ).count()
    if recent_count >= 2:
        findings.append(
            SignalFinding(
                "short_order_burst",
                "Multiple orders in a short period",
                "At least two other orders from this customer were placed in the prior 24 hours.",
                25,
            )
        )

    if order.payment_attempts >= 3:
        findings.append(
            SignalFinding(
                "repeated_payment_attempts",
                "Repeated payment attempts",
                f"{order.payment_attempts} payment attempts were recorded for this order.",
                20,
            )
        )

    local_hour = timezone.localtime(order.ordered_at).hour
    if 0 <= local_hour < 5:
        findings.append(
            SignalFinding(
                "unusual_transaction_time",
                "Unusual transaction timing",
                "The order was placed between midnight and 5:00 a.m. UTC.",
                15,
            )
        )

    score = min(sum(signal.points for signal in findings), 100)
    return RiskAssessment(score, classify_risk(score), tuple(findings))


def recalculate_order_risk(order: Order) -> RiskAssessment:
    """Persist a fresh assessment and replace the order's prior signal records."""
    assessment = assess_order(order)
    order.risk_score = assessment.score
    order.risk_level = assessment.level
    order.save(update_fields=["risk_score", "risk_level", "updated_at"])
    order.signals.all().delete()
    RiskSignal.objects.bulk_create(
        [
            RiskSignal(
                order=order,
                code=signal.code,
                label=signal.label,
                description=signal.description,
                points=signal.points,
            )
            for signal in assessment.signals
        ]
    )
    return assessment