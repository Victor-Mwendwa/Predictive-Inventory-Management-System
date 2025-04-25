# tests/test_views.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Product, Retailer, Inventory, Order, OrderItem, DemandForecast
import json
from datetime import datetime, timedelta
from django.utils import timezone

class ViewTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        
        # Create test client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test data
        self.product = Product.objects.create(
            name="Test Product",
            category="Beverages",
            unit_price=100.50
        )
        
        self.retailer = Retailer.objects.create(
            name="Test Retailer",
            location="Nairobi"
        )
        
        self.inventory = Inventory.objects.create(
            product=self.product,
            current_stock=100,
            safety_stock_threshold=20
        )
        
        self.order = Order.objects.create(
            retailer=self.retailer,
            status="pending"
        )
        
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=5,
            unit_price=self.product.unit_price
        )
        
        self.forecast = DemandForecast.objects.create(
            product=self.product,
            predicted_demand=42.5,
            forecast_date=timezone.now().date() + timedelta(days=1),
            confidence_score=85.0
        )

    # Authentication Tests
    def test_login_required_views(self):
        views = [
            reverse('dashboard'),
            reverse('product_list'),
            reverse('order_list'),
            reverse('low_stock')
        ]
        
        # Test logged out user
        self.client.logout()
        for url in views:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Test logged in user
        self.client.login(username='testuser', password='testpass123')
        for url in views:
            response = self.client.get(url)
            self.assertIn(response.status_code, [200, 302])  # 302 for possible redirects

    # Dashboard View Tests
    def test_dashboard_view(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Test Product")
        self.assertTemplateUsed(response, 'core/dashboard.html')

    # Product View Tests
    def test_product_list_view(self):
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertTemplateUsed(response, 'core/product_list.html')

    def test_product_create_view(self):
        response = self.client.post(reverse('product_create'), {
            'name': 'New Product',
            'category': 'Snacks',
            'unit_price': 50.00,
            'cost_price': 30.00
        })
        self.assertEqual(response.status_code, 302)  # Redirect after creation
        self.assertTrue(Product.objects.filter(name='New Product').exists())

    def test_product_update_view(self):
        url = reverse('product_update', args=[self.product.id])
        response = self.client.post(url, {
            'name': 'Updated Product',
            'category': 'Beverages',
            'unit_price': 110.00
        })
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Updated Product')

    # Inventory View Tests
    def test_inventory_list_view(self):
        response = self.client.get(reverse('stock_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "100")
        self.assertTemplateUsed(response, 'core/stock_list.html')

    def test_low_stock_view(self):
        # First test with current stock (should be empty)
        response = self.client.get(reverse('low_stock'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Test Product")
        
        # Set stock to low and test again
        self.inventory.current_stock = 10
        self.inventory.save()
        response = self.client.get(reverse('low_stock'))
        self.assertContains(response, "Test Product")

    # Order View Tests
    def test_order_list_view(self):
        response = self.client.get(reverse('order_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Retailer")
        self.assertTemplateUsed(response, 'core/order_list.html')

    def test_order_create_view(self):
        response = self.client.post(reverse('order_create'), {
            'retailer': self.retailer.id,
            'order_items-TOTAL_FORMS': '1',
            'order_items-INITIAL_FORMS': '0',
            'order_items-0-product': self.product.id,
            'order_items-0-quantity': '10'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 2)
        new_order = Order.objects.latest('id')
        self.assertEqual(new_order.order_items.count(), 1)

    # Forecast View Tests
    def test_forecast_list_view(self):
        response = self.client.get(reverse('forecast_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "42.5")
        self.assertTemplateUsed(response, 'core/forecast_list.html')

    def test_generate_forecasts_view(self):
        # Mock the actual forecasting task for testing
        from unittest.mock import patch
        with patch('core.tasks.generate_demand_forecasts.delay') as mock_task:
            response = self.client.post(reverse('generate_forecasts'))
            self.assertEqual(response.status_code, 302)
            mock_task.assert_called_once()

    # API View Tests
    def test_inventory_api_view(self):
        response = self.client.get('/api/inventory/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['product_name'], "Test Product")

    def test_low_stock_api_view(self):
        # Test with normal stock
        response = self.client.get('/api/inventory/low-stock/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 0)
        
        # Test with low stock
        self.inventory.current_stock = 10
        self.inventory.save()
        response = self.client.get('/api/inventory/low-stock/')
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)

    # Form Validation Tests
    def test_invalid_product_creation(self):
        response = self.client.post(reverse('product_create'), {
            'name': '',  # Invalid - empty name
            'category': 'Invalid',
            'unit_price': -10  # Invalid - negative price
        })
        self.assertEqual(response.status_code, 200)  # Returns form with errors
        self.assertContains(response, "This field is required")
        self.assertContains(response, "Ensure this value is greater than or equal to 0")

    def test_invalid_order_creation(self):
        response = self.client.post(reverse('order_create'), {
            'retailer': self.retailer.id,
            'order_items-TOTAL_FORMS': '1',
            'order_items-INITIAL_FORMS': '0',
            'order_items-0-product': self.product.id,
            'order_items-0-quantity': '-5'  # Invalid - negative quantity
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ensure this value is greater than or equal to 1")

    # Permission Tests
    def test_staff_permission_required(self):
        # Create non-staff user
        non_staff = User.objects.create_user(
            username='regularuser',
            password='testpass123',
            is_staff=False
        )
        self.client.login(username='regularuser', password='testpass123')
        
        protected_urls = [
            reverse('product_create'),
            reverse('generate_forecasts')
        ]
        
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)  # Forbidden