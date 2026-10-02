from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from orders.models import InvestigationNote, Order
from orders.serializers import (
    ExplanationRequestSerializer,
    InvestigationNoteCreateSerializer,
    InvestigationNoteSerializer,
    InvestigationUpdateSerializer,
    OrderSerializer,
    RiskSignalSerializer,
)
from orders.services.ai_explainer import (
    AIExplanationUnavailable,
    generate_order_explanation,
)


def order_queryset():
    return (
        Order.objects.select_related("customer")
        .prefetch_related("items", "signals", "notes")
    )


class DashboardSummaryAPIView(APIView):
    def get(self, request):
        summary = Order.objects.aggregate(
            total=Count("id"),
            low=Count("id", filter=Q(risk_level=Order.RiskLevel.LOW)),
            medium=Count("id", filter=Q(risk_level=Order.RiskLevel.MEDIUM)),
            high=Count("id", filter=Q(risk_level=Order.RiskLevel.HIGH)),
            average_score=Avg("risk_score"),
        )
        summary["average_score"] = round(summary["average_score"] or 0, 1)
        summary["generated_at"] = timezone.now()
        return Response(summary)


class OrderListAPIView(APIView):
    def get(self, request):
        orders = order_queryset()
        query = request.query_params.get("q", "").strip()
        risk_level = request.query_params.get("risk_level", "").strip().lower()
        sort = request.query_params.get("sort", "newest")

        if query:
            orders = orders.filter(
                Q(order_number__icontains=query)
                | Q(customer__name__icontains=query)
                | Q(customer__customer_id__icontains=query)
                | Q(payment_method__icontains=query)
            )
        if risk_level in Order.RiskLevel.values:
            orders = orders.filter(risk_level=risk_level)

        sort_fields = {
            "newest": "-ordered_at",
            "oldest": "ordered_at",
            "risk": "-risk_score",
            "amount": "-amount",
        }
        orders = orders.order_by(sort_fields.get(sort, "-ordered_at"), "-id")
        return Response(OrderSerializer(orders[:100], many=True).data)


class OrderDetailAPIView(APIView):
    def get(self, request, pk):
        order = get_object_or_404(order_queryset(), pk=pk)
        return Response(OrderSerializer(order).data)


class OrderRiskAPIView(APIView):
    def get(self, request, pk):
        order = get_object_or_404(order_queryset(), pk=pk)
        return Response(
            {
                "order_id": order.order_number,
                "risk_score": order.risk_score,
                "risk_level": order.risk_level,
                "risk_level_label": order.get_risk_level_display(),
                "signals": RiskSignalSerializer(order.signals.all(), many=True).data,
            }
        )


class OrderExplanationAPIView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai_explanation"

    def post(self, request, pk):
        order = get_object_or_404(order_queryset(), pk=pk)
        serializer = ExplanationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        regenerate = serializer.validated_data["regenerate"]

        if order.ai_explanation and not regenerate:
            return Response(
                {
                    "explanation": order.ai_explanation,
                    "generated_at": order.ai_explanation_generated_at,
                    "cached": True,
                }
            )

        try:
            explanation = generate_order_explanation(order)
        except AIExplanationUnavailable as exc:
            return Response(
                {
                    "detail": str(exc),
                    "explanation": order.ai_explanation or None,
                    "cached": bool(order.ai_explanation),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            # Keep provider details, payloads and credentials out of responses and logs.
            import logging

            logging.getLogger("orders.ai").warning(
                "Unexpected explanation error for order %s (%s)",
                order.order_number,
                type(exc).__name__,
            )
            return Response(
                {
                    "detail": "AI explanation is temporarily unavailable. Please try again shortly.",
                    "explanation": order.ai_explanation or None,
                    "cached": bool(order.ai_explanation),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        order.ai_explanation = explanation
        order.ai_explanation_generated_at = timezone.now()
        order.save(
            update_fields=[
                "ai_explanation",
                "ai_explanation_generated_at",
                "updated_at",
            ]
        )
        return Response(
            {
                "explanation": explanation,
                "generated_at": order.ai_explanation_generated_at,
                "cached": False,
            },
            status=status.HTTP_201_CREATED,
        )


class InvestigationUpdateAPIView(APIView):
    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        serializer = InvestigationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.investigation_status = serializer.validated_data["status"]
        order.save(update_fields=["investigation_status", "updated_at"])
        return Response(
            {
                "status": order.investigation_status,
                "status_label": order.get_investigation_status_display(),
            }
        )


class InvestigationNoteCreateAPIView(APIView):
    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        serializer = InvestigationNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = InvestigationNote.objects.create(order=order, **serializer.validated_data)
        return Response(
            InvestigationNoteSerializer(note).data,
            status=status.HTTP_201_CREATED,
        )