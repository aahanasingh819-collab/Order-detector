from rest_framework import serializers

from orders.models import InvestigationNote, Order, OrderItem, RiskSignal


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("product_name", "category", "quantity", "unit_price")


class RiskSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskSignal
        fields = ("code", "label", "description", "points")


class InvestigationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestigationNote
        fields = ("id", "note", "created_by", "created_at")
        read_only_fields = ("id", "created_at")


class OrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_id = serializers.CharField(source="customer.customer_id", read_only=True)
    risk_level_label = serializers.CharField(source="get_risk_level_display", read_only=True)
    investigation_status_label = serializers.CharField(
        source="get_investigation_status_display", read_only=True
    )
    items = OrderItemSerializer(many=True, read_only=True)
    signals = RiskSignalSerializer(many=True, read_only=True)
    notes = InvestigationNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "customer_id",
            "customer_name",
            "amount",
            "ordered_at",
            "payment_method",
            "payment_attempts",
            "delivery_address",
            "risk_score",
            "risk_level",
            "risk_level_label",
            "investigation_status",
            "investigation_status_label",
            "ai_explanation",
            "ai_explanation_generated_at",
            "items",
            "signals",
            "notes",
        )


class ExplanationRequestSerializer(serializers.Serializer):
    regenerate = serializers.BooleanField(default=False)


class InvestigationUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.InvestigationStatus.choices)


class InvestigationNoteCreateSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(max_length=100, required=False, default="Reviewer")

    class Meta:
        model = InvestigationNote
        fields = ("note", "created_by")

    def validate_note(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Add a little more detail to the note.")
        return value