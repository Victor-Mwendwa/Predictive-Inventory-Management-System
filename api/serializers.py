from rest_framework import serializers
from core.models import Product  # Adjust if your model is somewhere else
from rest_framework import serializers
from core.models import Inventory
from rest_framework import serializers
from core.models import Order
from rest_framework import serializers
from core.models import Retailer
from rest_framework import serializers
from core.models import DemandForecast
from rest_framework import serializers
from core.models import Order

class DemandForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandForecast
        fields = '__all__'
        
class RetailerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Retailer
        fields = '__all__'
        
class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        
class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = '__all__'
        
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
        
class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'