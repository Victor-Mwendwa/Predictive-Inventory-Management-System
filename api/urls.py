# api/urls.py
from django.urls import path
from . import views
from rest_framework.authtoken.views import obtain_auth_token
from django.urls import path
from core.views import InventoryList
from .views import InventoryList
from django.urls import path, include
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from django.urls import path, include
from .views import ForecastList 
from .views import (
    ProductViewSet,
    InventoryViewSet,
    OrderViewSet,
    RetailerViewSet,
    DemandForecastViewSet,
    generate_forecasts,
    QRScan
)

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'inventory', InventoryViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'retailers', RetailerViewSet)
router.register(r'forecasts', DemandForecastViewSet)

urlpatterns = [
    path('auth/', obtain_auth_token, name='api_token_auth'),
    path('forecasts/generate/', generate_forecasts, name='generate_forecasts'),
    path('qr/scan/', QRScan.as_view(), name='qr_scan'),
    path('', include(router.urls)),
  
    
    # Authentication
    path('auth/', obtain_auth_token, name='api_token_auth'),
    
    # Inventory API
    path('inventory/', views.InventoryList.as_view(), name='inventory_list'),
    path('inventory/<int:pk>/', views.InventoryDetail.as_view(), name='inventory_detail'),
    path('inventory/low-stock/', views.LowStockList.as_view(), name='low_stock_list'),
    
    # Product API
    path('products/', views.ProductList.as_view(), name='product_list'),
    path('products/<int:pk>/', views.ProductDetail.as_view(), name='product_detail'),
    
    # Order API
    path('orders/', views.OrderList.as_view(), name='order_list'),
    path('orders/<int:pk>/', views.OrderDetail.as_view(), name='order_detail'),
    
    # Forecast API
    path('forecasts/', views.ForecastList.as_view(), name='forecast_list'),
    path('forecasts/generate/', views.GenerateForecasts.as_view(), name='generate_forecasts'),
    
    # QR Code integration
    path('qr/scan/', views.QRScan.as_view(), name='qr_scan'),
]

