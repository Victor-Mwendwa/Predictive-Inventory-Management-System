from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import viewsets
from core.models import Product  # Adjust the import path if necessary
from .serializers import ProductSerializer  # Ensure this serializer exists
from core.models import Product  # Correct import if Product is in the same app
from rest_framework import viewsets
from core.models import Inventory
from api.serializers import InventorySerializer  # Ensure this serializer exists
from rest_framework import viewsets
from core.models import Order
from api.serializers import OrderSerializer  # Make sure this file exists!
from rest_framework import viewsets
from core.models import Retailer  # Make sure this model exists in core/models.py
from api.serializers import RetailerSerializer  # We'll handle this next
from rest_framework import viewsets
from core.models import DemandForecast
from api.serializers import DemandForecastSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets, views, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import ListView
from core.models import Inventory  
from django.views.generic import DetailView
from core.models import Inventory
from django.views.generic import ListView
from core.models import Inventory
from django.db.models import F
from django.views.generic import ListView
from core.models import Product
from django.views.generic import DetailView
from core.models import Product
from rest_framework.generics import RetrieveAPIView
from core.models import Product
from .serializers import ProductSerializer
from rest_framework.generics import ListAPIView
from core.models import Order
from .serializers import OrderSerializer
from rest_framework import viewsets
from core.models import Order
from .serializers import OrderSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from core.models import Inventory, Order, Product, DemandForecast
from .serializers import (
    InventorySerializer,
    OrderSerializer,
    ProductSerializer,
    DemandForecastSerializer,
)
from rest_framework.views import APIView
from rest_framework.response import Response

class GenerateForecasts(APIView):
    def post(self, request, *args, **kwargs):
        # your logic here
        return Response({"message": "Forecasts generated!"})
    
class InventoryList(generics.ListAPIView):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer

class InventoryDetail(generics.RetrieveAPIView):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer

class LowStockList(generics.ListAPIView):
    queryset = Inventory.objects.filter(current_stock__lte=F('reorder_point'))
    serializer_class = InventorySerializer

class ProductList(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class ProductDetail(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class OrderList(generics.ListAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

class OrderDetail(generics.RetrieveAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    
class ForecastList(ListAPIView):
    queryset = DemandForecast.objects.all()
    serializer_class = DemandForecastSerializer
    
def reports(request):
    # Your report generation logic here
    return HttpResponse('Reports page')

# ViewSets (used in router.register)
class ProductViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'message': 'List of products'})

class InventoryViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'message': 'Inventory list'})

class OrderViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'message': 'Orders list'})

class RetailerViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'message': 'Retailers list'})

class DemandForecastViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'message': 'Forecasts list'})

# API Views
class DashboardStatsView(views.APIView):
    def get(self, request):
        return Response({'message': 'Dashboard stats'})

class SalesReportView(views.APIView):
    def get(self, request):
        return Response({'message': 'Sales report'})

class InventoryReportView(views.APIView):
    def get(self, request):
        return Response({'message': 'Inventory report'})

class QRScan(APIView):
    def post(self, request):
        # Replace this logic with your QR scanning logic
        data = {"message": "QR code scanned successfully"}
        return Response(data)
    
# Function-based views
@api_view(['POST'])
def generate_forecasts(request):
    return Response({'message': 'Forecasts generated'})

@api_view(['POST'])
def bulk_inventory_update(request):
    return Response({'message': 'Inventory bulk update'})

@api_view(['GET'])
def export_orders_csv(request):
    return Response({'message': 'Orders exported to CSV'})

@api_view(['POST'])
def import_products_csv(request):
    return Response({'message': 'Products imported from CSV'})

# Optional health check view already in your urls
from django.http import JsonResponse

class InventoryList(ListView):
    model = Inventory
    template_name = 'api/inventory_list.html'
    context_object_name = 'inventory_items'
    
class InventoryDetail(DetailView):
    model = Inventory
    template_name = 'api/inventory_detail.html'  # You can customize the template
    context_object_name = 'inventory'
    
class LowStockList(ListView):
    model = Inventory
    template_name = 'api/low_stock_list.html'  # Create this template
    context_object_name = 'low_stock_items'
    
class ProductDetail(DetailView):
    model = Product
    template_name = 'api/product_detail.html'
    context_object_name = 'product'

    def get_queryset(self):
        return Inventory.objects.filter(current_stock__lte=F('reorder_point')).select_related('product')
    
class ProductList(ListView):
    model = Product
    template_name = 'api/product_list.html'  # create this template if needed
    context_object_name = 'products'
    
class ProductDetail(RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
class DemandForecastViewSet(viewsets.ModelViewSet):
    queryset = DemandForecast.objects.all()
    serializer_class = DemandForecastSerializer
    
class RetailerViewSet(viewsets.ModelViewSet):
    queryset = Retailer.objects.all()
    serializer_class = RetailerSerializer
    
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    
class InventoryViewSet(viewsets.ModelViewSet):
    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer
    
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
class OrderList(ListAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

@api_view(["GET"])
def test_api(request):
    return Response({"message": "API is working!"})
