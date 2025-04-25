# api/routes.py
from django.urls import path, include
from django.http import JsonResponse

# Move these out of any function so they exist at import time:
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter

# Your DRF viewsets and APIViews:
from .views import (
    ProductViewSet,
    InventoryViewSet,
    OrderViewSet,
    RetailerViewSet,
    DemandForecastViewSet,
    DashboardStatsView,
    SalesReportView,
    InventoryReportView,
    generate_forecasts,
    bulk_inventory_update,
    export_orders_csv,
    import_products_csv,
)

api_router  = DefaultRouter()
api_router .register(r'products', ProductViewSet, basename='product')
api_router .register(r'inventory', InventoryViewSet, basename='inventory')
api_router .register(r'orders', OrderViewSet, basename='order')
api_router .register(r'retailers', RetailerViewSet, basename='retailer')
api_router .register(r'forecasts', DemandForecastViewSet, basename='forecast')

urlpatterns = [
    # Authentication
    path('token/',    TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Dashboard
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # Reports
    path('reports/sales/',    SalesReportView.as_view(), name='sales-report'),
    path('reports/inventory/', InventoryReportView.as_view(), name='inventory-report'),

    # Forecasts
    path('forecasts/generate/', generate_forecasts, name='generate-forecasts'),

    # Bulk Operations
    path('inventory/bulk-update/', bulk_inventory_update, name='bulk-inventory-update'),
    path('orders/export-csv/',      export_orders_csv,    name='export-orders-csv'),
    path('products/import-csv/',    import_products_csv,  name='import-products-csv'),

    # Health Check
    path('health/', lambda req: JsonResponse({'status': 'ok'}), name='health-check'),
] + api_router .urls
