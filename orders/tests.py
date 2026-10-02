from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from orders.models import Customer, InvestigationNote, Order, RiskSignal
from orders.services.risk_engine import (
    assess_order,
    classify_risk,
    recalculate_order_risk,
)


class RiskEngineTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.customer = Customer.objects.create(
            customer_id="CUST-TEST-01",
            name="Demo Reviewer",
            email="reviewer@example.test",
            registered_at=now - timedelta(days=365),
        )
        self.home = "10 Fictional Lane, Sampleton"
        Order.objects.create(
            order_number="OD-HISTORY-1",
            customer=self.customer,
            amount=Decimal("100.00"),
            ordered_at=now - timedelta(days=35),
            payment_method="Visa ending 1284",
            delivery_address=self.home,
        )

    def make_order(self, **kwargs):
        values = {
            "order_number": "OD-TEST-1",
            "customer": self.customer,
            "amount": Decimal("100.00"),
            "ordered_at": timezone.now(),
            "payment_method": "Visa ending 1284",
            "payment_attempts": 1,
            "delivery_address": self.home,
        }
        values.update(kwargs)
        return Order.objects.create(**values)

    def test_risk_level_boundaries_and_clamping(self):
        self.assertEqual(classify_risk(-10), Order.RiskLevel.LOW)
        self.assertEqual(classify_risk(0), Order.RiskLevel.LOW)
        self.assertEqual(classify_risk(30), Order.RiskLevel.LOW)
        self.assertEqual(classify_risk(31), Order.RiskLevel.MEDIUM)
        self.assertEqual(classify_risk(60), Order.RiskLevel.MEDIUM)
        self.assertEqual(classify_risk(61), Order.RiskLevel.HIGH)
        self.assertEqual(classify_risk(120), Order.RiskLevel.HIGH)

    def test_normal_order_has_no_signals(self):
        order = self.make_order()
        assessment = assess_order(order)
        self.assertEqual(assessment.score, 0)
        self.assertEqual(assessment.level, Order.RiskLevel.LOW)
        self.assertEqual(assessment.signals, ())

    def test_multiple_observed_signals_produce_bounded_high_score(self):
        target = timezone.now().replace(hour=2, minute=30, second=0, microsecond=0)
        for suffix, hour_offset in (("A", 1), ("B", 3)):
            Order.objects.create(
                order_number=f"OD-RECENT-{suffix}",
                customer=self.customer,
                amount=Decimal("80.00"),
                ordered_at=target - timedelta(hours=hour_offset),
                payment_method="Visa ending 1284",
                delivery_address=self.home,
            )
        order = self.make_order(
            amount=Decimal("300.00"),
            ordered_at=target,
            payment_attempts=3,
            delivery_address="72 New Avenue, Sampleton",
        )
        assessment = assess_order(order)
        self.assertEqual(assessment.score, 100)
        self.assertEqual(assessment.level, Order.RiskLevel.HIGH)
        codes = {signal.code for signal in assessment.signals}
        self.assertIn("unusually_high_amount", codes)
        self.assertIn("new_delivery_address", codes)
        self.assertIn("short_order_burst", codes)
        self.assertIn("repeated_payment_attempts", codes)
        self.assertIn("unusual_transaction_time", codes)

    def test_recalculation_persists_score_and_signals(self):
        order = self.make_order(amount=Decimal("270.00"))
        first = recalculate_order_risk(order)
        self.assertEqual(order.risk_score, first.score)
        self.assertTrue(RiskSignal.objects.filter(order=order).exists())
        first_signal_count = order.signals.count()
        second = recalculate_order_risk(order)
        self.assertEqual(first.score, second.score)
        self.assertEqual(order.signals.count(), first_signal_count)


class OrderApplicationTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.customer = Customer.objects.create(
            customer_id="CUST-API-01",
            name="Demo Customer",
            email="customer@example.test",
            registered_at=now - timedelta(days=180),
        )
        self.order = Order.objects.create(
            order_number="OD-API-1001",
            customer=self.customer,
            amount=Decimal("149.95"),
            ordered_at=now - timedelta(minutes=10),
            payment_method="Mastercard ending 4811",
            payment_attempts=1,
            delivery_address="18 Example Road, Sampleton",
            risk_score=20,
            risk_level=Order.RiskLevel.LOW,
        )
        self.client = APIClient()

    def test_dashboard_and_order_detail_render(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Order review")
        self.assertContains(response, self.order.order_number)

        detail = self.client.get(reverse("order-detail", args=[self.order.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Customer behaviour")
        self.assertContains(detail, "Risk analysis")

    def test_unknown_order_returns_not_found(self):
        response = self.client.get(reverse("order-detail", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_order_list_filter_and_risk_endpoint(self):
        response = self.client.get("/risk-api/v1/orders/?q=API-1001&risk_level=low")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["order_number"], self.order.order_number)

        risk = self.client.get(f"/risk-api/v1/orders/{self.order.pk}/risk/")
        self.assertEqual(risk.status_code, 200)
        self.assertEqual(risk.data["risk_score"], 20)
        self.assertEqual(risk.data["risk_level"], Order.RiskLevel.LOW)

    def test_summary_endpoint_handles_existing_and_empty_counts(self):
        response = self.client.get("/risk-api/v1/dashboard/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["average_score"], 20)

    def test_status_update_and_note_creation(self):
        status_response = self.client.patch(
            f"/risk-api/v1/orders/{self.order.pk}/investigation/",
            {"status": Order.InvestigationStatus.UNDER_REVIEW},
            format="json",
        )
        self.assertEqual(status_response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(
            self.order.investigation_status, Order.InvestigationStatus.UNDER_REVIEW
        )

        note_response = self.client.post(
            f"/risk-api/v1/orders/{self.order.pk}/notes/",
            {"note": "Address checked against prior orders."},
            format="json",
        )
        self.assertEqual(note_response.status_code, 201)
        self.assertEqual(InvestigationNote.objects.filter(order=self.order).count(), 1)
        self.assertEqual(note_response.data["created_by"], "Reviewer")

    @override_settings(GEMINI_API_KEY="")
    def test_missing_gemini_key_returns_clear_service_unavailable(self):
        response = self.client.post(
            f"/risk-api/v1/orders/{self.order.pk}/explanation/",
            {"regenerate": False},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("currently unavailable", response.data["detail"])
        self.assertNotIn("GEMINI_API_KEY", response.data)

    @patch(
        "orders.api_views.generate_order_explanation",
        return_value="The order has a new address; a reviewer should verify it.",
    )
    def test_explanation_is_stored_and_reused_without_another_call(self, explain):
        url = f"/risk-api/v1/orders/{self.order.pk}/explanation/"
        generated = self.client.post(url, {"regenerate": False}, format="json")
        self.assertEqual(generated.status_code, 201)
        self.assertFalse(generated.data["cached"])

        cached = self.client.post(url, {"regenerate": False}, format="json")
        self.assertEqual(cached.status_code, 200)
        self.assertTrue(cached.data["cached"])
        self.assertEqual(explain.call_count, 1)