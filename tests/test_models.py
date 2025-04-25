# tests/test_models.py
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import Product, Retailer, Inventory, Order, OrderItem, DemandForecast, Supplier
from datetime import datetime, timedelta
import pytz

class ProductModelTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Product",
            category="Beverages",
            description="Test description",
            unit_price=100.50,
            cost_price=70.25,
            min_order_quantity=5,
            lead_time_days=7,
            perishable=True,
            expiry_days=30
        )

    def test_product_creation(self):
        self.assertEqual(self.product.name, "Test Product")
        self.assertEqual(self.product.category, "Beverages")
        self.assertEqual(self.product.unit_price, 100.50)
        self.assertTrue(self.product.perishable)
        self.assertEqual(self.product.expiry_days, 30)

    def test_product_str_representation(self):
        self.assertEqual(str(self.product), "Test Product (Beverages)")

    def test_product_profit_margin(self):
        expected_margin = ((100.50 - 70.25) / 100.50) * 100
        self.assertAlmostEqual(self.product.profit_margin, expected_margin, places=2)

    def test_non_perishable_product(self):
        product = Product.objects.create(
            name="Non-Perishable",
            category="Household",
            perishable=False
        )
        self.assertIsNone(product.expiry_days)

    def test_negative_prices(self):
        with self.assertRaises(ValidationError):
            Product.objects.create(
                name="Invalid Product",
                category="Test",
                unit_price=-10,
                cost_price=5
            )

class RetailerModelTest(TestCase):
    def setUp(self):
        self.retailer = Retailer.objects.create(
            name="Test Retailer",
            location="Nairobi",
            contact="0712345678",
            storage_capacity=500
        )

    def test_retailer_creation(self):
        self.assertEqual(self.retailer.name, "Test Retailer")
        self.assertEqual(self.retailer.location, "Nairobi")
        self.assertEqual(self.retailer.account_balance, 0)  # Default value

    def test_retailer_str_representation(self):
        self.assertEqual(str(self.retailer), "Test Retailer (Nairobi)")

class InventoryModelTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Inventory Product",
            category="Snacks"
        )
        self.inventory = Inventory.objects.create(
            product=self.product,
            current_stock=100,
            safety_stock_threshold=20
        )

    def test_inventory_creation(self):
        self.assertEqual(self.inventory.current_stock, 100)
        self.assertEqual(self.inventory.safety_stock_threshold, 20)
        self.assertEqual(self.inventory.product.name, "Inventory Product")

    def test_inventory_str_representation(self):
        expected_str = f"Inventory for {self.product.name}: 100 units"
        self.assertEqual(str(self.inventory), expected_str)

    def test_low_stock_property(self):
        # Test when stock is above threshold
        self.assertFalse(self.inventory.is_low_stock)
        
        # Test when stock is below threshold
        self.inventory.current_stock = 15
        self.assertTrue(self.inventory.is_low_stock)

    def test_stock_adjustment(self):
        # Test adding stock
        self.inventory.adjust_stock(50)
        self.assertEqual(self.inventory.current_stock, 150)
        
        # Test removing stock
        self.inventory.adjust_stock(-30)
        self.assertEqual(self.inventory.current_stock, 120)
        
        # Test cannot go below zero
        with self.assertRaises(ValidationError):
            self.inventory.adjust_stock(-200)

class OrderModelTest(TestCase):
    def setUp(self):
        self.retailer = Retailer.objects.create(
            name="Order Retailer",
            location="Mombasa"
        )
        self.product1 = Product.objects.create(
            name="Product 1",
            category="Beverages",
            unit_price=150
        )
        self.product2 = Product.objects.create(
            name="Product 2",
            category="Snacks",
            unit_price=80
        )
        
        self.order = Order.objects.create(
            retailer=self.retailer,
            order_date=datetime.now(pytz.UTC),
            status="pending"
        )
        
        OrderItem.objects.create(
            order=self.order,
            product=self.product1,
            quantity=10,
            unit_price=self.product1.unit_price
        )
        
        OrderItem.objects.create(
            order=self.order,
            product=self.product2,
            quantity=5,
            unit_price=self.product2.unit_price
        )

    def test_order_creation(self):
        self.assertEqual(self.order.retailer.name, "Order Retailer")
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(self.order.order_items.count(), 2)

    def test_order_total_calculation(self):
        expected_total = (10 * 150) + (5 * 80)
        self.assertEqual(self.order.total, expected_total)

    def test_order_status_transitions(self):
        # Test valid transitions
        self.order.status = "completed"
        self.order.save()
        self.assertEqual(self.order.status, "completed")
        
        # Test invalid status
        with self.assertRaises(ValidationError):
            self.order.status = "invalid_status"
            self.order.full_clean()

    def test_order_item_creation(self):
        item = self.order.order_items.first()
        self.assertEqual(item.quantity, 10)
        self.assertEqual(item.line_total, 10 * 150)

class DemandForecastModelTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Forecast Product",
            category="Dairy"
        )
        self.forecast_date = datetime.now(pytz.UTC).date() + timedelta(days=1)
        self.forecast = DemandForecast.objects.create(
            product=self.product,
            predicted_demand=42.5,
            forecast_date=self.forecast_date,
            confidence_score=85.0,
            model_metrics="MAE: 3.2, R2: 0.89"
        )

    def test_forecast_creation(self):
        self.assertEqual(self.forecast.product.name, "Forecast Product")
        self.assertEqual(self.forecast.predicted_demand, 42.5)
        self.assertEqual(self.forecast.forecast_date, self.forecast_date)

    def test_forecast_str_representation(self):
        expected_str = f"Forecast for {self.product.name} on {self.forecast_date}: 42.5 units"
        self.assertEqual(str(self.forecast), expected_str)

    def test_confidence_score_validation(self):
        # Test valid confidence score
        self.forecast.confidence_score = 100
        self.forecast.full_clean()
        
        # Test invalid confidence score (>100)
        with self.assertRaises(ValidationError):
            self.forecast.confidence_score = 105
            self.forecast.full_clean()
        
        # Test invalid confidence score (<0)
        with self.assertRaises(ValidationError):
            self.forecast.confidence_score = -5
            self.forecast.full_clean()

class SupplierModelTest(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Test Supplier",
            contact="0722333444",
            lead_time_days=7,
            reliability_score=4.5
        )

    def test_supplier_creation(self):
        self.assertEqual(self.supplier.name, "Test Supplier")
        self.assertEqual(self.supplier.lead_time_days, 7)
        self.assertEqual(self.supplier.reliability_score, 4.5)

    def test_supplier_str_representation(self):
        self.assertEqual(str(self.supplier), "Test Supplier (Lead time: 7 days)")

    def test_reliability_score_validation(self):
        # Test valid score
        self.supplier.reliability_score = 5.0
        self.supplier.full_clean()
        
        # Test invalid score (>5)
        with self.assertRaises(ValidationError):
            self.supplier.reliability_score = 5.1
            self.supplier.full_clean()
        
        # Test invalid score (<0)
        with self.assertRaises(ValidationError):
            self.supplier.reliability_score = -0.1
            self.supplier.full_clean()

class ModelRelationshipsTest(TestCase):
    def test_inventory_product_relationship(self):
        product = Product.objects.create(name="Test Product")
        inventory = Inventory.objects.create(product=product, current_stock=50)
        
        self.assertEqual(inventory.product, product)
        self.assertEqual(product.inventory, inventory)

    def test_order_retailer_relationship(self):
        retailer = Retailer.objects.create(name="Test Retailer")
        order = Order.objects.create(retailer=retailer)
        
        self.assertEqual(order.retailer, retailer)
        self.assertEqual(retailer.orders.count(), 1)

    def test_order_item_relationships(self):
        product = Product.objects.create(name="Test Product")
        retailer = Retailer.objects.create(name="Test Retailer")
        order = Order.objects.create(retailer=retailer)
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=5,
            unit_price=100
        )
        
        self.assertEqual(item.order, order)
        self.assertEqual(item.product, product)
        self.assertEqual(order.order_items.count(), 1)
        self.assertEqual(product.order_items.count(), 1)