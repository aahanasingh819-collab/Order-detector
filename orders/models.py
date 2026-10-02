from django.db import models


class Customer(models.Model):
    customer_id = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    registered_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.customer_id})"


class Order(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "low", "Low risk"
        MEDIUM = "medium", "Medium risk"
        HIGH = "high", "High risk"

    class InvestigationStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        UNDER_REVIEW = "under_review", "Under review"
        REVIEWED = "reviewed", "Reviewed"

    order_number = models.CharField(max_length=24, unique=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="orders"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    ordered_at = models.DateTimeField()
    payment_method = models.CharField(max_length=40)
    payment_attempts = models.PositiveSmallIntegerField(default=1)
    delivery_address = models.CharField(max_length=240)
    risk_score = models.PositiveSmallIntegerField(default=0)
    risk_level = models.CharField(
        max_length=8, choices=RiskLevel.choices, default=RiskLevel.LOW, db_index=True
    )
    investigation_status = models.CharField(
        max_length=16,
        choices=InvestigationStatus.choices,
        default=InvestigationStatus.PENDING,
        db_index=True,
    )
    ai_explanation = models.TextField(blank=True)
    ai_explanation_generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ordered_at", "-id"]
        indexes = [
            models.Index(fields=["risk_level", "-ordered_at"]),
            models.Index(fields=["investigation_status", "-ordered_at"]),
        ]

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class RiskSignal(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="signals")
    code = models.SlugField(max_length=40)
    label = models.CharField(max_length=100)
    description = models.CharField(max_length=240)
    points = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["-points", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "code"], name="unique_risk_signal_per_order"
            )
        ]

    def __str__(self):
        return f"{self.label} (+{self.points})"


class InvestigationNote(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notes")
    note = models.TextField(max_length=2000)
    created_by = models.CharField(max_length=100, default="Reviewer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Note on {self.order.order_number}"