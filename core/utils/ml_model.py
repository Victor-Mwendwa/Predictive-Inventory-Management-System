import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
import joblib
from datetime import datetime, timedelta
import holidays
import logging
from django.db.models import Sum, F, Q
from ..models import OrderItem, Product, DemandForecast
import os
from config import settings

logger = logging.getLogger(__name__)

class DemandForecaster:
    """
    Machine learning model for demand forecasting with enhanced features
    """
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.features = None
        self.model_path = os.path.join(settings.BASE_DIR, 'data', 'demand_model.pkl')
        self.scaler_path = os.path.join(settings.BASE_DIR, 'data', 'demand_scaler.pkl')
        self.features_path = os.path.join(settings.BASE_DIR, 'data', 'demand_features.pkl')
        self.kenya_holidays = holidays.Kenya()
        self.load_model()

    def load_model(self):
        """Load trained model and preprocessing objects from disk"""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.features = joblib.load(self.features_path)
                logger.info("Loaded trained model from disk")
            else:
                self._initialize_new_model()
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            self._initialize_new_model()

    def _initialize_new_model(self):
        """Initialize a new model with default parameters"""
        logger.info("Initializing new demand forecasting model")
        
        # Define preprocessing pipeline
        numeric_features = ['price', 'lag_7', 'lag_30', 'rolling_mean_7', 'rolling_std_7']
        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        
        categorical_features = ['day_of_week', 'month', 'is_holiday', 'is_weekend']
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='most_frequent')),
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        self.preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numeric_features),
                ('cat', categorical_transformer, categorical_features)
            ])
        
        # Initialize model with ensemble of regressors
        self.model = Pipeline(steps=[
            ('preprocessor', self.preprocessor),
            ('regressor', GradientBoostingRegressor(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=5,
                random_state=42
            ))
        ])
        
        # Initialize feature list
        self.features = numeric_features + categorical_features

    def save_model(self):
        """Save trained model and preprocessing objects to disk"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        try:
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            joblib.dump(self.features, self.features_path)
            logger.info("Saved model to disk")
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")

    def prepare_training_data(self):
        """
        Prepare training data from historical orders with enhanced features
        Returns X, y ready for training
        """
        logger.info("Preparing training data")
        
        # Get historical order data with additional context
        order_items = OrderItem.objects.select_related(
            'product', 'order'
        ).filter(
            order__order_date__gte=datetime.now() - timedelta(days=365)
        ).values(
            'product_id',
            'order__order_date',
            'quantity',
            'unit_price'
        )
        
        if not order_items:
            logger.warning("No historical data available for training")
            return None, None
        
        # Convert to DataFrame
        df = pd.DataFrame(list(order_items))
        df['date'] = pd.to_datetime(df['order__order_date'])
        df = df.drop(columns=['order__order_date'])
        
        # Feature engineering
        df = self._add_time_features(df)
        df = self._add_lag_features(df)
        df = self._add_rolling_features(df)
        df = self._add_holiday_features(df)
        
        # Drop rows with missing values from lag features
        df = df.dropna()
        
        if df.empty:
            logger.warning("Insufficient data after feature engineering")
            return None, None
        
        # Prepare X and y
        X = df[self.features]
        y = df['quantity']
        
        return X, y

    def _add_time_features(self, df):
        """Add temporal features to the dataset"""
        df['day_of_week'] = df['date'].dt.dayofweek
        df['month'] = df['date'].dt.month
        df['day_of_month'] = df['date'].dt.day
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        return df

    def _add_lag_features(self, df):
        """Add lagged sales features"""
        df = df.sort_values(['product_id', 'date'])
        
        # Product-specific lag features
        df['lag_7'] = df.groupby('product_id')['quantity'].shift(7)
        df['lag_30'] = df.groupby('product_id')['quantity'].shift(30)
        
        return df

    def _add_rolling_features(self, df):
        """Add rolling statistics features"""
        df = df.sort_values(['product_id', 'date'])
        
        # Rolling statistics
        df['rolling_mean_7'] = df.groupby('product_id')['quantity'].rolling(7).mean().reset_index(level=0, drop=True)
        df['rolling_std_7'] = df.groupby('product_id')['quantity'].rolling(7).std().reset_index(level=0, drop=True)
        df['rolling_max_7'] = df.groupby('product_id')['quantity'].rolling(7).max().reset_index(level=0, drop=True)
        
        return df

    def _add_holiday_features(self, df):
        """Add holiday-related features"""
        df['is_holiday'] = df['date'].apply(
            lambda x: x in self.kenya_holidays
        ).astype(int)
        return df

    def train_model(self, test_size=0.2):
        """
        Train the forecasting model with time-series cross-validation
        Returns trained model and evaluation metrics
        """
        X, y = self.prepare_training_data()
        
        if X is None or y is None:
            logger.error("Training aborted - no valid data")
            return None, None
        
        # Time-series cross-validation
        tscv = TimeSeriesSplit(n_splits=5)
        metrics = {'mae': [], 'rmse': []}
        
        for train_index, test_index in tscv.split(X):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            
            self.model.fit(X_train, y_train)
            y_pred = self.model.predict(X_test)
            
            metrics['mae'].append(mean_absolute_error(y_test, y_pred))
            metrics['rmse'].append(np.sqrt(mean_squared_error(y_test, y_pred)))
        
        # Final training on all data
        self.model.fit(X, y)
        self.save_model()
        
        avg_mae = np.mean(metrics['mae'])
        avg_rmse = np.mean(metrics['rmse'])
        
        logger.info(f"Model trained - Avg MAE: {avg_mae:.2f}, Avg RMSE: {avg_rmse:.2f}")
        return self.model, {'mae': avg_mae, 'rmse': avg_rmse}

    def predict_demand(self, product_id, forecast_date):
        """
        Predict demand for a specific product on a future date
        Returns predicted demand and confidence score
        """
        if not isinstance(forecast_date, datetime):
            forecast_date = datetime.strptime(forecast_date, '%Y-%m-%d')
        
        # Get product data
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.error(f"Product {product_id} not found")
            return None, None
        
        # Get historical data for feature generation
        order_items = OrderItem.objects.filter(
            product=product
        ).select_related('order').order_by('order__order_date')
        
        if not order_items.exists():
            logger.warning(f"No historical data for product {product_id}")
            return None, None
        
        # Prepare features for prediction
        features = self._prepare_prediction_features(product, order_items, forecast_date)
        X_pred = pd.DataFrame([features])
        
        # Ensure we have all expected features
        for col in self.features:
            if col not in X_pred.columns:
                X_pred[col] = 0
        
        # Reorder columns to match training
        X_pred = X_pred[self.features]
        
        # Make prediction
        try:
            predicted_demand = max(0, round(self.model.predict(X_pred)[0]))
            
            # Simple confidence estimation based on data availability
            confidence = self._calculate_confidence(product, order_items.count())
            
            return predicted_demand, confidence
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            return None, None

    def _prepare_prediction_features(self, product, order_items, forecast_date):
        """Prepare feature vector for prediction"""
        last_date = order_items.last().order.order_date.date()
        days_to_forecast = (forecast_date.date() - last_date).days
        
        # Base features
        features = {
            'product_id': product.id,
            'price': float(product.price),
            'day_of_week': forecast_date.weekday(),
            'month': forecast_date.month,
            'day_of_month': forecast_date.day,
            'is_weekend': int(forecast_date.weekday() >= 5),
            'is_holiday': int(forecast_date.date() in self.kenya_holidays)
        }
        
        # Calculate lag features
        last_7_days = last_date - timedelta(days=7)
        last_30_days = last_date - timedelta(days=30)
        
        qty_7 = order_items.filter(
            order__order_date__date__gte=last_7_days,
            order__order_date__date__lte=last_date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        qty_30 = order_items.filter(
            order__order_date__date__gte=last_30_days,
            order__order_date__date__lte=last_date
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        features.update({
            'lag_7': qty_7,
            'lag_30': qty_30
        })
        
        # Calculate rolling statistics
        rolling_mean = order_items.filter(
            order__order_date__date__gte=last_date - timedelta(days=7)
        ).aggregate(avg=Sum('quantity')/7)['avg'] or 0
        
        rolling_std = np.std([item.quantity for item in 
                            order_items.filter(
                                order__order_date__date__gte=last_date - timedelta(days=7)
                            )][:7] or [0])
        
        features.update({
            'rolling_mean_7': rolling_mean,
            'rolling_std_7': rolling_std
        })
        
        return features

    def _calculate_confidence(self, product, historical_data_points):
        """Calculate confidence score based on data quality"""
        base_confidence = min(90, historical_data_points * 2)  # 2% per data point up to 90%
        
        # Adjust for inventory age
        if hasattr(product, 'inventory'):
            days_of_supply = product.inventory.days_of_supply
            if days_of_supply < 7:
                base_confidence += 5  # Bonus for fast-moving items
            elif days_of_supply > 30:
                base_confidence -= 10  # Penalty for slow-moving items
        
        return max(50, min(95, base_confidence))  # Keep between 50-95%

    def generate_forecasts(self, days_ahead=30, products=None):
        """
        Generate demand forecasts for all products or specified products
        Returns list of created forecasts
        """
        forecast_date = datetime.now().date() + timedelta(days=days_ahead)
        forecasts = []
        
        if products is None:
            products = Product.objects.all()
        
        for product in products:
            predicted_demand, confidence = self.predict_demand(product.id, forecast_date)
            
            if predicted_demand is not None:
                forecast = DemandForecast(
                    product=product,
                    predicted_demand=predicted_demand,
                    confidence_score=confidence,
                    forecast_date=forecast_date,
                    algorithm_version='v2.0'
                )
                forecasts.append(forecast)
        
        if forecasts:
            try:
                created = DemandForecast.objects.bulk_create(forecasts)
                logger.info(f"Created {len(created)} new forecasts")
                return created
            except Exception as e:
                logger.error(f"Error saving forecasts: {str(e)}")
                return []
        
        return []

    def evaluate_model(self):
        """
        Evaluate model performance on recent data
        Returns evaluation metrics
        """
        # Get recent data not used in training
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_items = OrderItem.objects.filter(
            order__order_date__gte=cutoff_date
        ).select_related('product', 'order')
        
        if not recent_items:
            return {'error': 'No recent data available'}
        
        # Prepare evaluation data
        eval_data = []
        for item in recent_items:
            predicted, _ = self.predict_demand(
                item.product.id,
                item.order.order_date
            )
            
            if predicted is not None:
                eval_data.append({
                    'product': item.product.name,
                    'actual': item.quantity,
                    'predicted': predicted,
                    'date': item.order.order_date
                })
        
        if not eval_data:
            return {'error': 'No valid predictions generated'}
        
        df = pd.DataFrame(eval_data)
        metrics = {
            'mae': mean_absolute_error(df['actual'], df['predicted']),
            'rmse': np.sqrt(mean_squared_error(df['actual'], df['predicted'])),
            'smape': self._calculate_smape(df['actual'], df['predicted']),
            'coverage': len(df) / len(recent_items) * 100
        }
        
        return metrics

    def _calculate_smape(self, actual, predicted):
        """Calculate Symmetric Mean Absolute Percentage Error"""
        return 100/len(actual) * np.sum(2 * np.abs(predicted - actual) / (np.abs(actual) + np.abs(predicted)))