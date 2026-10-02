from django.contrib import admin
from django.urls import include, path

from orders import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("orders/<int:pk>/", views.order_detail, name="order-detail"),
    path("risk-api/v1/", include("orders.api_urls")),
]