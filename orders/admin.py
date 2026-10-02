from django.contrib import admin

from orders.models import Customer, InvestigationNote, Order, OrderItem, RiskSignal


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class RiskSignalInline(admin.TabularInline):
    model = RiskSignal
    extra = 0
    readonly_fields = ("code", "label", "description", "points")
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_id", "name", "email", "registered_at")
    search_fields = ("customer_id", "name", "email")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "amount",
        "risk_score",
        "risk_level",
        "investigation_status",
        "ordered_at",
    )
    list_filter = ("risk_level", "investigation_status", "payment_method")
    search_fields = ("order_number", "customer__name", "customer__customer_id")
    readonly_fields = ("risk_score", "risk_level", "created_at", "updated_at")
    inlines = (OrderItemInline, RiskSignalInline)


@admin.register(InvestigationNote)
class InvestigationNoteAdmin(admin.ModelAdmin):
    list_display = ("order", "created_by", "created_at")
    search_fields = ("order__order_number", "note", "created_by")