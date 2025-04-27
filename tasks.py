from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib
import os
from django.conf import settings
from core.models import Product, Inventory, Order, DemandForecast
from core.utils.ml_model import preprocess_data, evaluate_model
import numpy as np

logger = get_task_logger(__name__)

# Path to store trained models
MODELS_DIR = os.path.join(settings.BASE_DIR, 'data', 'ml_models')
os.makedirs(MODELS_DIR, exist_ok=True)

@shared_task(bind=True)
def generate_demand_forecasts(self, product_ids=None, forecast_days=30):
    """
    Generate demand forecasts for products using machine learning
    Args:
        product_ids: List of product IDs to forecast (None for all products)
        forecast_days: Number of days to forecast ahead
    """
    logger.info("Starting demand forecast generation")
    
    try:
        # Get products to forecast (all if None specified)
        products = Product.objects.all()
        if product_ids:
            products = products.filter(id__in=product_ids)
        
        forecast_results = []
        
        for product in products:
            try:
                # Get historical data for this product
                orders = Order.objects.filter(
                    product=product,
                    order_date__gte=datetime.now() - timedelta(days=365)
                ).values('order_date', 'quantity')
                
                if len(orders) < 30:  # Not enough data
                    logger.warning(f"Insufficient data for product {product.id}, skipping")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(list(orders))
                df['order_date'] = pd.to_datetime(df['order_date'])
                df = df.set_index('order_date').resample('D').sum().fillna(0)
                
                # Preprocess data
                X, y, dates = preprocess_data(df)
                
                # Train/test split (80/20)
                split = int(0.8 * len(X))
                X_train, X_test = X[:split], X[split:]
                y_train, y_test = y[:split], y[split:]
                
                # Train model
                model = RandomForestRegressor(n_estimators=100, random_state=42)
                model.fit(X_train, y_train)
                
                # Evaluate
                mae, mse, r2 = evaluate_model(model, X_test, y_test)
                logger.info(f"Product {product.id} - MAE: {mae:.2f}, MSE: {mse:.2f}, R2: {r2:.2f}")
                
                # Generate forecasts
                last_data = X[-1].reshape(1, -1)
                forecast = []
                
                for _ in range(forecast_days):
                    pred = model.predict(last_data)[0]
                    forecast.append(max(0, pred))  # Ensure non-negative
                    # Update last_data with the prediction
                    last_data = np.roll(last_data, -1)
                    last_data[0, -1] = pred
                
                # Save model
                model_path = os.path.join(MODELS_DIR, f"product_{product.id}_model.pkl")
                joblib.dump(model, model_path)
                
                # Create forecast records
                forecast_date = datetime.now().date()
                for i, quantity in enumerate(forecast):
                    forecast_day = forecast_date + timedelta(days=i+1)
                    
                    DemandForecast.objects.update_or_create(
                        product=product,
                        forecast_date=forecast_day,
                        defaults={
                            'predicted_demand': quantity,
                            'confidence_score': r2 * 100,  # Convert R2 to percentage
                            'model_metrics': f"MAE: {mae:.2f}, MSE: {mse:.2f}",
                            'model_path': model_path
                        }
                    )
                
                forecast_results.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'metrics': {'mae': mae, 'mse': mse, 'r2': r2},
                    'forecast_days': forecast_days
                })
                
            except Exception as e:
                logger.error(f"Error forecasting for product {product.id}: {str(e)}")
                continue
        
        logger.info(f"Completed demand forecasts for {len(forecast_results)} products")
        return forecast_results
        
    except Exception as e:
        logger.error(f"Failed to generate forecasts: {str(e)}")
        raise self.retry(exc=e, countdown=60)

@shared_task
def check_low_stock():
    """
    Check inventory levels and generate alerts for low stock
    """
    logger.info("Checking for low stock items")
    
    try:
        low_stock_items = []
        inventory_items = Inventory.objects.select_related('product').all()
        
        for item in inventory_items:
            # Get latest forecast
            forecast = DemandForecast.objects.filter(
                product=item.product
            ).order_by('-forecast_date').first()
            
            safety_stock = item.safety_stock_threshold or 0
            days_of_cover = 7  # Default value
            
            if forecast and forecast.predicted_demand > 0:
                # Calculate days of inventory cover based on forecast
                days_of_cover = item.current_stock / (forecast.predicted_demand / 30)  # Convert monthly to daily
                
            if days_of_cover < safety_stock or item.current_stock <= 0:
                low_stock_items.append({
                    'product_id': item.product.id,
                    'product_name': item.product.name,
                    'current_stock': item.current_stock,
                    'safety_stock': safety_stock,
                    'days_of_cover': round(days_of_cover, 1)
                })
        
        logger.info(f"Found {len(low_stock_items)} low stock items")
        return low_stock_items
        
    except Exception as e:
        logger.error(f"Error checking low stock: {str(e)}")
        raise

@shared_task
def process_auto_reorders():
    """
    Process automatic reorders based on inventory levels and forecasts
    """
    logger.info("Processing automatic reorders")
    
    try:
        # First check for low stock
        low_stock_result = check_low_stock.delay()
        low_stock_items = low_stock_result.get()
        
        reorders_created = []
        
        for item in low_stock_items:
            product = Product.objects.get(id=item['product_id'])
            
            # Get latest forecast
            forecast = DemandForecast.objects.filter(
                product=product
            ).order_by('-forecast_date').first()
            
            if forecast:
                # Calculate reorder quantity (cover next 30 days)
                reorder_qty = max(
                    forecast.predicted_demand - item['current_stock'],
                    product.min_order_quantity or 1
                )
                
                # Create reorder (in a real system, this would create a purchase order)
                reorders_created.append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'reorder_quantity': reorder_qty,
                    'current_stock': item['current_stock'],
                    'forecast_demand': forecast.predicted_demand
                })
                
                logger.info(f"Created reorder for {product.name}: {reorder_qty} units")
        
        logger.info(f"Created {len(reorders_created)} automatic reorders")
        return reorders_created
        
    except Exception as e:
        logger.error(f"Error processing auto reorders: {str(e)}")
        raise

@shared_task
def update_inventory_from_sales(sales_data):
    """
    Update inventory levels from sales data
    Args:
        sales_data: List of dicts with product_id and quantity_sold
    """
    logger.info(f"Updating inventory from {len(sales_data)} sales records")
    
    try:
        updated_items = []
        
        for sale in sales_data:
            product_id = sale.get('product_id')
            quantity_sold = sale.get('quantity_sold', 0)
            
            if not product_id or quantity_sold <= 0:
                continue
            
            try:
                # Update inventory (atomic operation to prevent race conditions)
                inventory = Inventory.objects.select_for_update().get(product_id=product_id)
                inventory.current_stock = max(0, inventory.current_stock - quantity_sold)
                inventory.save()
                
                updated_items.append({
                    'product_id': product_id,
                    'new_stock': inventory.current_stock
                })
                
            except Inventory.DoesNotExist:
                logger.warning(f"No inventory record for product {product_id}")
                continue
        
        logger.info(f"Updated {len(updated_items)} inventory records")
        return updated_items
        
    except Exception as e:
        logger.error(f"Error updating inventory: {str(e)}")
        raise

@shared_task
def daily_maintenance():
    """
    Daily maintenance tasks to run
    """
    logger.info("Starting daily maintenance tasks")
    
    try:
        # Generate forecasts for all products
        forecast_task = generate_demand_forecasts.delay()
        
        # Check for low stock
        low_stock_task = check_low_stock.delay()
        
        # Process automatic reorders
        reorder_task = process_auto_reorders.delay()
        
        # Wait for all tasks to complete
        forecasts = forecast_task.get()
        low_stock = low_stock_task.get()
        reorders = reorder_task.get()
        
        return {
            'forecasts_generated': len(forecasts),
            'low_stock_items': len(low_stock),
            'reorders_created': len(reorders)
        }
        
    except Exception as e:
        logger.error(f"Error in daily maintenance: {str(e)}")
        raise