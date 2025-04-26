from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
import uuid

class ProductCategory(models.Model):
    """Category for grouping products"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Product Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Product model representing items in inventory"""
    PERISHABLE_CHOICES = [
        (True, 'Yes'),
        (False, 'No'),
    ]

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    category = models.ForeignKey(
        ProductCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products'
    )
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    perishable = models.BooleanField(choices=PERISHABLE_CHOICES, default=False)
    expiry_days = models.PositiveIntegerField(null=True, blank=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['sku']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def current_stock(self):
        """Get current stock level from related inventory"""
        if hasattr(self, 'inventory'):
            return self.inventory.current_stock
        return 0

    @property
    def monthly_sales(self):
        """Calculate total sales for the last 30 days"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        total = OrderItem.objects.filter(
            product=self,
            order__order_date__gte=thirty_days_ago
        ).aggregate(total=Sum('quantity'))['total']
        return total or 0

    @property
    def is_low_stock(self):
        """Check if product is below reorder point"""
        if hasattr(self, 'inventory'):
            return self.inventory.current_stock <= self.inventory.reorder_point
        return False


class Retailer(models.Model):
    """Retailer model representing store owners"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='retailer')
    name = models.CharField(
        max_length=255,
        blank=True,           # allow empty strings
        default='',           # default for existing rows
    )
    location = models.CharField(max_length=255)
    storage_capacity = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Storage capacity in cubic meters"
    )
    contact = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.username} - {self.location}"

    @property
    def monthly_order_volume(self):
        """Calculate total order volume for the last 30 days"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        total = Order.objects.filter(
            retailer=self,
            order_date__gte=thirty_days_ago
        ).count()
        return total


class Inventory(models.Model):
    """Inventory model tracking stock levels"""
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    current_stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current quantity in stock"
    )
    safety_stock = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Minimum stock level to maintain"
    )
    reorder_point = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0)],
        help_text="Stock level at which to reorder"
    )
    last_restocked = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Inventory"
        ordering = ['product__name']

    def __str__(self):
        return f"{self.product.name} - Stock: {self.current_stock}"

    @property
    def needs_restock(self):
        """Check if inventory needs restocking"""
        return self.current_stock <= self.reorder_point

    @property
    def days_of_supply(self):
        """Estimate days until stockout based on recent sales"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        total_sold = OrderItem.objects.filter(
            product=self.product,
            order__order_date__gte=thirty_days_ago
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        if total_sold > 0:
            daily_sales = total_sold / 30
            return round(self.current_stock / daily_sales, 1) if daily_sold > 0 else float('inf')
        return float('inf')


class Order(models.Model):
    """Order model representing retailer purchases"""
    ORDER_STATUS = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    retailer = models.ForeignKey(
        Retailer,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS,
        default='PENDING'
    )
    order_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    reference = models.CharField(max_length=50, unique=True, default=uuid.uuid4)

    class Meta:
        ordering = ['-order_date']
        indexes = [
            models.Index(fields=['retailer']),
            models.Index(fields=['status']),
            models.Index(fields=['order_date']),
        ]

    def __str__(self):
        return f"Order #{self.reference} - {self.retailer.user.username}"

    @property
    def total(self):
        """Calculate total order value"""
        return sum(item.subtotal for item in self.items.all())

    @property
    def item_count(self):
        """Count of items in the order"""
        return self.items.count()

    def update_status(self, new_status):
        """Update order status with validation"""
        valid_transitions = {
            'PENDING': ['PROCESSING', 'CANCELLED'],
            'PROCESSING': ['SHIPPED', 'CANCELLED'],
            'SHIPPED': ['DELIVERED'],
        }
        
        if new_status in valid_transitions.get(self.status, []):
            self.status = new_status
            self.save()
            return True
        return False


class OrderItem(models.Model):
    """Items within an order"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['order', 'product']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.quantity} x {self.product.name} @ {self.unit_price}"

    @property
    def subtotal(self):
        """Calculate line item total"""
        return self.quantity * self.unit_price

    def save(self, *args, **kwargs):
        """Override save to update inventory"""
        if not self.pk:  # New order item being created
            # Update inventory
            inventory = self.product.inventory
            inventory.current_stock -= self.quantity
            inventory.save()
        super().save(*args, **kwargs)


class DemandForecast(models.Model):
    """Machine learning generated demand forecasts"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='forecasts'
    )
    predicted_demand = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Predicted units needed"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Model confidence percentage"
    )
    forecast_date = models.DateField(
        help_text="Date this forecast applies to"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    algorithm_version = models.CharField(max_length=50, default='v1.0')

    class Meta:
        ordering = ['-forecast_date']
        unique_together = ['product', 'forecast_date']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['forecast_date']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.predicted_demand} units ({self.forecast_date})"

    @property
    def suggested_order_quantity(self):
        """Calculate suggested order quantity based on forecast"""
        inventory = self.product.inventory
        if inventory:
            needed = self.predicted_demand - inventory.current_stock
            return max(0, needed)
        return self.predicted_demand


class InventoryAudit(models.Model):
    """Audit trail for inventory changes"""
    ACTION_CHOICES = [
        ('RESTOCK', 'Restock'),
        ('SALE', 'Sale'),
        ('ADJUSTMENT', 'Adjustment'),
        ('RETURN', 'Return'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.IntegerField(
        help_text="Positive for additions, negative for deductions"
    )
    previous_quantity = models.IntegerField()
    new_quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} - {self.product.name} ({self.quantity})"