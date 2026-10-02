from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Customer, Order, OrderItem
from orders.services.risk_engine import recalculate_order_risk


PROFILES = [
    ("Avery Morgan", "low"),
    ("Jordan Ellis", "low"),
    ("Riley Bennett", "low"),
    ("Casey Parker", "low"),
    ("Morgan Reed", "low"),
    ("Taylor Quinn", "low"),
    ("Cameron Blake", "medium_amount"),
    ("Drew Harper", "medium_amount"),
    ("Skyler Rowan", "medium_amount"),
    ("Finley Brooks", "medium_amount"),
    ("Alex Monroe", "medium_payment"),
    ("Jamie Ellis", "medium_payment"),
    ("Robin Hayes", "high"),
    ("Sage Cooper", "high"),
    ("Emerson Lane", "high"),
    ("Peyton Riley", "high"),
    ("Dakota Blair", "low"),
    ("Reese Sutton", "low"),
]

PRODUCTS = [
    ("Wireless headphones", "Electronics"),
    ("Everyday backpack", "Accessories"),
    ("Ceramic coffee set", "Home"),
    ("Running shoes", "Apparel"),
    ("Portable monitor", "Electronics"),
]


class Command(BaseCommand):
    help = "Create fictional customers and orders for the Order Detector demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing orders and customers before creating demo data.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            Order.objects.all().delete()
            Customer.objects.all().delete()
        elif Order.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Orders already exist; leaving data unchanged. Use --reset to replace the demo dataset."
                )
            )
            return

        now = timezone.localtime(timezone.now())
        created_orders = 0
        for index, (name, profile) in enumerate(PROFILES, start=1):
            customer_id = f"CUST-{index:04d}"
            customer = Customer.objects.create(
                customer_id=customer_id,
                name=name,
                email=f"{name.lower().replace(' ', '.')}@example.test",
                registered_at=now - timedelta(days=260 + index * 11),
            )
            baseline = Decimal(72 + (index % 6) * 21)
            home = f"{120 + index} Cedar Street, Sampleton"
            high_profile = profile == "high"
            current_time = now - timedelta(minutes=index * 17)
            if high_profile:
                current_time = now.replace(hour=2, minute=36, second=0, microsecond=0)
                if current_time > now:
                    current_time -= timedelta(days=1)

            history_count = 1 + (index % 3)
            for prior_index in range(history_count):
                prior_time = current_time - timedelta(days=32 + prior_index * 24)
                prior_amount = (baseline * Decimal("0.88" + str(prior_index % 3))).quantize(
                    Decimal("0.01")
                )
                self._create_order(
                    customer=customer,
                    order_number=f"OD-{index:03d}-H{prior_index + 1}",
                    amount=prior_amount,
                    ordered_at=prior_time,
                    payment_method=("Visa ending 1284", "Mastercard ending 4811")[
                        prior_index % 2
                    ],
                    payment_attempts=1,
                    address=home,
                    product_index=(index + prior_index) % len(PRODUCTS),
                    status=Order.InvestigationStatus.REVIEWED,
                )
                created_orders += 1

            if high_profile:
                for recent_index, hours_ago in enumerate((7, 3), start=1):
                    self._create_order(
                        customer=customer,
                        order_number=f"OD-{index:03d}-R{recent_index}",
                        amount=(baseline * Decimal("0.95")).quantize(Decimal("0.01")),
                        ordered_at=current_time - timedelta(hours=hours_ago),
                        payment_method="Visa ending 1284",
                        payment_attempts=1,
                        address=home,
                        product_index=(index + recent_index) % len(PRODUCTS),
                        status=Order.InvestigationStatus.PENDING,
                    )
                    created_orders += 1

            amount = baseline
            address = home
            attempts = 1
            if profile == "medium_amount":
                amount = (baseline * Decimal("2.10")).quantize(Decimal("0.01"))
                address = f"{44 + index} Birch Avenue, Sampleton"
            elif profile == "medium_payment":
                address = f"{44 + index} Birch Avenue, Sampleton"
                attempts = 3
            elif high_profile:
                amount = (baseline * Decimal("3.1")).quantize(Decimal("0.01"))
                address = f"{44 + index} Birch Avenue, Sampleton"
                attempts = 4

            investigation_status = (
                Order.InvestigationStatus.UNDER_REVIEW
                if index in (7, 11, 14)
                else Order.InvestigationStatus.PENDING
            )
            self._create_order(
                customer=customer,
                order_number=f"OD-{index:03d}-01",
                amount=amount,
                ordered_at=current_time,
                payment_method=("Visa ending 1284", "PayPal", "Mastercard ending 4811")[
                    index % 3
                ],
                payment_attempts=attempts,
                address=address,
                product_index=index % len(PRODUCTS),
                status=investigation_status,
            )
            created_orders += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(PROFILES)} fictional customers and {created_orders} demo orders."
            )
        )

    @staticmethod
    def _create_order(
        *,
        customer,
        order_number,
        amount,
        ordered_at,
        payment_method,
        payment_attempts,
        address,
        product_index,
        status,
    ):
        order = Order.objects.create(
            order_number=order_number,
            customer=customer,
            amount=amount,
            ordered_at=ordered_at,
            payment_method=payment_method,
            payment_attempts=payment_attempts,
            delivery_address=address,
            investigation_status=status,
        )
        name, category = PRODUCTS[product_index]
        OrderItem.objects.create(
            order=order,
            product_name=name,
            category=category,
            quantity=1 + (product_index % 2),
            unit_price=amount,
        )
        recalculate_order_risk(order)
        return order