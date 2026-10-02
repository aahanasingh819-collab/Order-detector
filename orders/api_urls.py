from django.urls import path
from django.views.decorators.csrf import csrf_protect

from orders import api_views

urlpatterns = [
    path("dashboard/summary/", api_views.DashboardSummaryAPIView.as_view(), name="api-summary"),
    path("orders/", api_views.OrderListAPIView.as_view(), name="api-order-list"),
    path("orders/<int:pk>/", api_views.OrderDetailAPIView.as_view(), name="api-order-detail"),
    path("orders/<int:pk>/risk/", api_views.OrderRiskAPIView.as_view(), name="api-order-risk"),
    path(
        "orders/<int:pk>/explanation/",
        csrf_protect(api_views.OrderExplanationAPIView.as_view()),
        name="api-order-explanation",
    ),
    path(
        "orders/<int:pk>/investigation/",
        csrf_protect(api_views.InvestigationUpdateAPIView.as_view()),
        name="api-investigation-update",
    ),
    path(
        "orders/<int:pk>/notes/",
        csrf_protect(api_views.InvestigationNoteCreateAPIView.as_view()),
        name="api-investigation-note",
    ),
]