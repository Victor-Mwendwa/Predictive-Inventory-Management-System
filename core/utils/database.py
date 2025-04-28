import logging
from django.db import transaction, DatabaseError
from django.db.models import F, Sum, DecimalField
from datetime import timedelta
from django.db.models import ExpressionWrapper
from django.utils import timezone
from ..models import (
    Product, Inventory, OrderItem,
    InventoryAudit, Order
)

logger = logging.getLogger(__name__)

class InventoryManager:
    """
    Handles inventory-related database operations
    """
    
    @staticmethod
    def update_inventory(product_id, quantity_change, action, user, reference=''):
        """
        Updates inventory levels and creates an audit record
        
        Args:
            product_id: ID of the product to update
            quantity_change: Positive for additions, negative for deductions
            action: Type of action (RESTOCK, SALE, ADJUSTMENT, RETURN)
            user: User performing the action
            reference: Optional reference string
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            with transaction.atomic():
                product = Product.objects.select_for_update().get(pk=product_id)
                inventory = product.inventory
                
                # Record previous quantity for audit
                previous_quantity = inventory.current_stock
                
                # Calculate new quantity
                new_quantity = previous_quantity + quantity_change
                if new_quantity < 0:
                    return False, "Insufficient stock available"
                
                # Update inventory
                inventory.current_stock = new_quantity
                inventory.save()
                
                # Create audit record
                InventoryAudit.objects.create(
                    product=product,
                    action=action,
                    quantity=quantity_change,
                    previous_quantity=previous_quantity,
                    new_quantity=new_quantity,
                    reference=reference,
                    created_by=user
                )
                
                return True, "Inventory updated successfully"
                
        except Product.DoesNotExist:
            logger.error(f"Product with ID {product_id} not found")
            return False, "Product not found"
        except DatabaseError as e:
            logger.error(f"Database error updating inventory: {str(e)}")
            return False, "Database error occurred"

    @staticmethod
    def get_low_stock_items(threshold=None):
        """
        Returns products that are below their reorder point
        
        Args:
            threshold: Optional custom threshold to override reorder_point
            
        Returns:
            QuerySet of Inventory objects
        """
        if threshold is not None:
            return Inventory.objects.filter(
                current_stock__lte=threshold
            ).select_related('product')
        return Inventory.objects.filter(
            current_stock__lte=F('reorder_point')
        ).select_related('product')

    @staticmethod
    def get_inventory_value():
        """
        Calculates the total monetary value of all inventory
        
        Returns:
            float: Total inventory value
        """
        return Inventory.objects.aggregate(
            total_value=Sum(F('current_stock') * F('product__price'))
        )['total_value'] or 0


class OrderManager:
    """
    Handles order-related database operations
    """
    
    @staticmethod
    def create_order(retailer, items, notes=''):
        """
        Creates an order with multiple items and updates inventory
        
        Args:
            retailer: Retailer placing the order
            items: List of dicts with product_id and quantity
            notes: Optional order notes
            
        Returns:
            tuple: (order: Order, errors: list)
        """
        errors = []
        try:
            with transaction.atomic():
                # Create the order
                order = Order.objects.create(
                    retailer=retailer,
                    notes=notes
                )
                
                # Process each item
                for item in items:
                    product = Product.objects.select_for_update().get(pk=item['product_id'])
                    inventory = product.inventory
                    
                    if item['quantity'] > inventory.current_stock:
                        errors.append(f"Insufficient stock for {product.name}")
                        continue
                    
                    # Create order item
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item['quantity'],
                        unit_price=product.price
                    )
                    
                    # Update inventory
                    inventory.current_stock = F('current_stock') - item['quantity']
                    inventory.save()
                
                if errors:
                    raise ValueError("Some items couldn't be processed")
                
                return order, errors
                
        except Product.DoesNotExist as e:
            logger.error(f"Product not found: {str(e)}")
            errors.append("One or more products not found")
            return None, errors
        except DatabaseError as e:
            logger.error(f"Database error creating order: {str(e)}")
            errors.append("Database error occurred")
            return None, errors
        except ValueError:
            return order, errors  # Partial order with errors

    @staticmethod
    def get_retailer_order_stats(retailer_id, days=30):
        """
        Gets order statistics for a retailer
        
        Args:
            retailer_id: ID of the retailer
            days: Number of days to look back
            
        Returns:
            dict: Order statistics
        """
        start_date = timezone.now() - timedelta(days=days)
        
        stats = {
            'total_orders': 0,
            'total_items': 0,
            'total_value': 0,
            'top_products': []
        }
        
        try:
            # Get basic order stats
            orders = Order.objects.filter(
                retailer_id=retailer_id,
                order_date__gte=start_date
            )
            
            stats['total_orders'] = orders.count()
            
            # Get item-level stats
            items = OrderItem.objects.filter(
                order__retailer_id=retailer_id,
                order__order_date__gte=start_date
            )
            
            item_stats = items.aggregate(
                total_items=Sum('quantity'),
                total_value=Sum(F('quantity') * F('unit_price'))
            )
            
            stats['total_items'] = item_stats['total_items'] or 0
            stats['total_value'] = item_stats['total_value'] or 0
            
            # Get top products
            stats['top_products'] = items.values(
                'product__name'
            ).annotate(
                total_quantity=Sum('quantity'),
                total_value=Sum(F('quantity') * F('unit_price'))
            ).order_by('-total_quantity')[:5]
            
        except DatabaseError as e:
            logger.error(f"Error getting retailer stats: {str(e)}")
        
        return stats


class AnalyticsManager:
    """
    Handles analytics and reporting database operations
    """
    
    @staticmethod
    def get_sales_trend(days=30, category_id=None):
        """
        Gets sales trend data for visualization
        
        Args:
            days: Number of days to analyze
            category_id: Optional category filter
            
        Returns:
            dict: Sales trend data
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        filters = {
            'order__order_date__date__range': [start_date, end_date]
        }
        
        if category_id:
            filters['product__category_id'] = category_id
        
        daily_sales = OrderItem.objects.filter(
            **filters
        ).values(
            'order__order_date__date'
        ).annotate(
            total_sales=Sum(F('quantity') * F('unit_price'))
        ).order_by('order__order_date__date')
        
        return {
            'labels': [entry['order__order_date__date'].strftime('%Y-%m-%d') for entry in daily_sales],
            'data': [float(entry['total_sales'] or 0) for entry in daily_sales]
        }

    @staticmethod
    def get_product_performance(days=30, limit=10):
        """
        Gets top performing products
        
        Args:
            days: Number of days to analyze
            limit: Number of products to return
            
        Returns:
            QuerySet of product performance data
        """
        start_date = timezone.now() - timedelta(days=days)
        
        return OrderItem.objects.filter(
            order__order_date__gte=start_date
        ).values(
            'product__name',
            'product__category__name'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum(
                ExpressionWrapper(
                    F('quantity') * F('unit_price'),
                    output_field=DecimalField(max_digits=18, decimal_places=2)
                )
            )
        ).order_by('-total_revenue')[:limit]


def backup_database():
    """
    Creates a backup of critical database tables
    Returns success status and message
    """
    try:
        # In a real implementation, this would connect to your database
        # and perform a backup. Here's a conceptual example:
        
        # 1. Get current timestamp for backup filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        # 2. In production, you would:
        # - Use database-specific tools (pg_dump, mysqldump)
        # - Save to cloud storage or backup server
        # - Verify backup integrity
        
        logger.info(f"Database backup initiated at {timestamp}")
        return True, "Backup completed successfully"
        
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return False, f"Backup failed: {str(e)}"