from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import RegisterView

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Inventory management
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    
    # Inventory tracking
    path('stock/', views.stock_list, name='stock_list'),
    path('stock/low/', views.low_stock, name='low_stock'),
    path('stock/update/', views.stock_update, name='stock_update'),
    path('stock/out-of-stock/', views.out_of_stock, name='out_of_stock'),
    
    # Demand forecasting
    path('forecasts/', views.forecast_list, name='forecast_list'),
    path('forecasts/generate/', views.generate_forecasts, name='generate_forecasts'),
    path("forecasts/results/", views.forecast_results_view, name="forecast_results"),
    path('forecasts/produce/', views.forecast_ui_page, name='produce_forecasts'),
    path('forecasts/run-task/', views.trigger_forecast_task, name='run_forecast_task'),
    path("forecasts-table/", views.forecast_table_view, name="forecast_table"),

    # Reports
    path('forecast-report/', views.forecast_report, name='forecast_report'),
    path('reports/sales/', views.sales_report, name='sales_report'),
    path('reports/inventory/', views.inventory_report, name='inventory_report'),

    # Order management
    path('orders/', views.order_list, name='order_list'),
    path('orders/create/', views.order_create, name='order_create'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    
    # Automated reordering
    path('reorders/', views.reorder_list, name='reorder_list'),
    path('reorders/auto/', views.auto_reorder, name='auto_reorder'),
    path('reorders/manual/', views.manual_reorder, name='manual_reorder'),
    
    # Supplier management
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    
    # Retailers
    path('retailers/', views.retailer_list, name='retailer_list'),
    
    # Profile page
    path('profile/', views.profile, name='profile'),

    # Inventory report (duplicate corrected)
    path('inventory-report/', views.inventory_report, name='inventory_report'),

    path('low-stock/submit-to-finance/', views.submit_to_finance, name='submit_to_finance'),

]
