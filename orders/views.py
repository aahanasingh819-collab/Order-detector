from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import timedelta

from orders.models import Order


@ensure_csrf_cookie
def dashboard(request):
    orders = Order.objects.select_related("customer").prefetch_related("signals")
    query = request.GET.get("q", "").strip()
    risk_level = request.GET.get("risk", "").strip().lower()
    sort = request.GET.get("sort", "newest")

    if query:
        orders = orders.filter(
            Q(order_number__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(customer__customer_id__icontains=query)
            | Q(payment_method__icontains=query)
        )
    if risk_level in Order.RiskLevel.values:
        orders = orders.filter(risk_level=risk_level)

    sort_options = {
        "newest": ("-ordered_at", "-id"),
        "oldest": ("ordered_at", "id"),
        "risk": ("-risk_score", "-ordered_at"),
        "amount": ("-amount", "-ordered_at"),
    }
    orders = orders.order_by(*sort_options.get(sort, sort_options["newest"]))

    summary = Order.objects.aggregate(
        total=Count("id"),
        low=Count("id", filter=Q(risk_level=Order.RiskLevel.LOW)),
        medium=Count("id", filter=Q(risk_level=Order.RiskLevel.MEDIUM)),
        high=Count("id", filter=Q(risk_level=Order.RiskLevel.HIGH)),
        average_score=Avg("risk_score"),
    )
    summary["average_score"] = round(summary["average_score"] or 0, 1)
    page = Paginator(orders, 12).get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard.html",
        {
            "summary": summary,
            "page": page,
            "query": query,
            "selected_risk": risk_level,
            "selected_sort": sort,
            "risk_choices": Order.RiskLevel.choices,
        },
    )


@ensure_csrf_cookie
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer").prefetch_related(
            "items", "signals", "notes"
        ),
        pk=pk,
    )
    history = Order.objects.filter(customer=order.customer).exclude(pk=order.pk)
    previous_orders = history.filter(ordered_at__lt=order.ordered_at)
    previous_average = previous_orders.aggregate(value=Avg("amount"))["value"]
    previous_addresses = list(
        previous_orders.values_list("delivery_address", flat=True).distinct()[:5]
    )
    behaviour = {
        "previous_order_count": previous_orders.count(),
        "average_previous_order_value": previous_average,
        "recent_order_frequency": history.filter(
            ordered_at__gte=timezone.now() - timedelta(days=30)
        ).count(),
        "previous_delivery_addresses": previous_addresses,
        "previous_payment_attempts": previous_orders.aggregate(
            total=Sum("payment_attempts")
        )["total"]
        or 0,
    }
    return render(
        request,
        "order_detail.html",
        {
            "order": order,
            "behaviour": behaviour,
            "ai_enabled": bool(settings.OPENAI_API_KEY),
            "status_choices": Order.InvestigationStatus.choices,
        },
    )