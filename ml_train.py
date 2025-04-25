# ml_train.py
import os
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler
from statsmodels.tsa.seasonal import seasonal_decompose
import matplotlib.pyplot as plt
from django.conf import settings
from core.models import Order, Product

# Configure paths
MODELS_DIR = os.path.join(settings.BASE_DIR, 'data', 'ml_models')
os.makedirs(MODELS_DIR, exist_ok=True)
PLOTS_DIR = os.path.join(settings.BASE_DIR, 'data', 'ml_plots')
os.makedirs(PLOTS_DIR, exist_ok=True)

class DemandForecaster:
    def __init__(self, product_id, model_type='random_forest'):
        """
        Initialize forecaster for a specific product
        Args:
            product_id: ID of the product to forecast
            model_type: Type of model to use ('random_forest' or 'gradient_boosting')
        """
        self.product_id = product_id
        self.model_type = model_type
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.model = None
        self.best_params = None
        self.metrics = {}
        
        # Model file paths
        self.model_path = os.path.join(MODELS_DIR, f'product_{product_id}_model.pkl')
        self.scaler_path = os.path.join(MODELS_DIR, f'product_{product_id}_scaler.pkl')
        self.plot_path = os.path.join(PLOTS_DIR, f'product_{product_id}_forecast.png')

    def load_data(self, days=365):
        """
        Load historical order data for the product
        Args:
            days: Number of days of historical data to load
        Returns:
            DataFrame with order data
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        orders = Order.objects.filter(
            product_id=self.product_id,
            order_date__gte=start_date,
            order_date__lte=end_date
        ).values('order_date', 'quantity')
        
        if not orders:
            raise ValueError(f"No order data found for product {self.product_id}")
        
        df = pd.DataFrame(list(orders))
        df['order_date'] = pd.to_datetime(df['order_date'])
        df = df.set_index('order_date').sort_index()
        
        # Resample to daily frequency and fill missing dates
        df = df.resample('D').sum().fillna(0)
        
        return df

    def preprocess_data(self, df, window_size=30):
        """
        Prepare time series data for supervised learning
        Args:
            df: DataFrame with time series data
            window_size: Number of previous days to use as features
        Returns:
            X (features), y (target), dates (corresponding dates)
        """
        # Normalize the data
        values = df['quantity'].values.reshape(-1, 1)
        scaled_values = self.scaler.fit_transform(values)
        
        # Create lagged features
        X, y, dates = [], [], []
        for i in range(window_size, len(scaled_values)):
            X.append(scaled_values[i-window_size:i, 0])
            y.append(scaled_values[i, 0])
            dates.append(df.index[i])
        
        return np.array(X), np.array(y), dates

    def train_model(self, X, y, optimize=False):
        """
        Train the forecasting model
        Args:
            X: Features
            y: Target values
            optimize: Whether to perform hyperparameter optimization
        """
        if self.model_type == 'random_forest':
            model = RandomForestRegressor(random_state=42)
            param_dist = {
                'n_estimators': [50, 100, 200],
                'max_depth': [None, 10, 20, 30],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            }
        else:  # gradient_boosting
            model = GradientBoostingRegressor(random_state=42)
            param_dist = {
                'n_estimators': [50, 100, 200],
                'learning_rate': [0.01, 0.05, 0.1],
                'max_depth': [3, 5, 7],
                'min_samples_split': [2, 5, 10]
            }
        
        if optimize:
            # Time-series cross-validation
            tscv = TimeSeriesSplit(n_splits=5)
            
            # Randomized search for hyperparameters
            search = RandomizedSearchCV(
                model,
                param_distributions=param_dist,
                n_iter=10,
                scoring='neg_mean_squared_error',
                cv=tscv,
                random_state=42,
                n_jobs=-1
            )
            
            search.fit(X, y)
            self.model = search.best_estimator_
            self.best_params = search.best_params_
        else:
            self.model = model
            self.model.fit(X, y)
            self.best_params = model.get_params()

    def evaluate_model(self, X_test, y_test):
        """
        Evaluate model performance
        Args:
            X_test: Test features
            y_test: Test targets
        Returns:
            Dictionary of evaluation metrics
        """
        y_pred = self.model.predict(X_test)
        
        # Inverse transform to get actual values
        y_test_actual = self.scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
        y_pred_actual = self.scaler.inverse_transform(y_pred.reshape(-1, 1)).flatten()
        
        # Calculate metrics
        metrics = {
            'mae': mean_absolute_error(y_test_actual, y_pred_actual),
            'mse': mean_squared_error(y_test_actual, y_pred_actual),
            'rmse': np.sqrt(mean_squared_error(y_test_actual, y_pred_actual)),
            'r2': r2_score(y_test_actual, y_pred_actual),
            'mape': np.mean(np.abs((y_test_actual - y_pred_actual) / y_test_actual)) * 100
        }
        
        self.metrics = metrics
        return metrics

    def generate_forecast(self, X_last, days=30):
        """
        Generate future demand forecast
        Args:
            X_last: Most recent window of data
            days: Number of days to forecast
        Returns:
            Array of forecasted values
        """
        forecasts = []
        current_input = X_last.copy()
        
        for _ in range(days):
            # Predict next day
            pred = self.model.predict(current_input.reshape(1, -1))[0]
            forecasts.append(pred)
            
            # Update input window
            current_input = np.roll(current_input, -1)
            current_input[-1] = pred
        
        # Inverse transform to get actual values
        forecasts_actual = self.scaler.inverse_transform(
            np.array(forecasts).reshape(-1, 1)
        
        return forecasts_actual.flatten())

    def analyze_seasonality(self, df):
        """
        Analyze seasonality in the time series data
        Args:
            df: DataFrame with time series data
        Returns:
            Seasonal decomposition results
        """
        # Ensure weekly frequency (7 days)
        result = seasonal_decompose(
            df['quantity'],
            model='additive',
            period=7,
            extrapolate_trend='freq'
        )
        
        return result

    def save_model(self):
        """Save trained model and scaler to disk"""
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)

    def load_model(self):
        """Load trained model and scaler from disk"""
        self.model = joblib.load(self.model_path)
        self.scaler = joblib.load(self.scaler_path)
        return self.model is not None

    def plot_results(self, df, X, y, dates, forecast_days=30):
        """
        Plot actual vs predicted values and forecast
        Args:
            df: Original DataFrame
            X: Features
            y: Actual values
            dates: Corresponding dates
            forecast_days: Number of days to forecast
        """
        plt.figure(figsize=(12, 6))
        
        # Plot historical data
        plt.plot(df.index, df['quantity'], label='Actual Demand', color='blue')
        
        # Plot model predictions on training data
        y_pred = self.model.predict(X)
        y_pred_actual = self.scaler.inverse_transform(y_pred.reshape(-1, 1))
        plt.plot(dates, y_pred_actual, label='Model Fit', color='green', alpha=0.7)
        
        # Generate and plot forecast
        last_window = X[-1]
        forecast = self.generate_forecast(last_window, forecast_days)
        forecast_dates = pd.date_range(start=dates[-1] + timedelta(days=1), periods=forecast_days)
        plt.plot(forecast_dates, forecast, label='Forecast', color='red', linestyle='--')
        
        # Plot seasonality decomposition if enough data
        if len(df) > 90:  # At least 3 months of data
            try:
                result = self.analyze_seasonality(df)
                plt.figure(figsize=(12, 8))
                result.plot()
                seasonality_plot_path = os.path.join(PLOTS_DIR, f'product_{self.product_id}_seasonality.png')
                plt.savefig(seasonality_plot_path)
                plt.close()
            except Exception as e:
                print(f"Could not plot seasonality: {e}")
        
        plt.title(f'Demand Forecast for Product {self.product_id}')
        plt.xlabel('Date')
        plt.ylabel('Quantity')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(self.plot_path)
        plt.close()

def train_product_model(product_id, model_type='random_forest', days=365, window_size=30, optimize=False):
    """
    Complete training pipeline for a single product
    Args:
        product_id: ID of product to train model for
        model_type: Type of model to use
        days: Number of days of historical data to use
        window_size: Number of previous days to use as features
        optimize: Whether to perform hyperparameter optimization
    Returns:
        Dictionary with training results
    """
    try:
        # Initialize forecaster
        forecaster = DemandForecaster(product_id, model_type)
        
        # Load and prepare data
        df = forecaster.load_data(days)
        X, y, dates = forecaster.preprocess_data(df, window_size)
        
        # Split data (80/20)
        split = int(0.8 * len(X))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        # Train model
        forecaster.train_model(X_train, y_train, optimize)
        
        # Evaluate model
        metrics = forecaster.evaluate_model(X_test, y_test)
        
        # Save model and plots
        forecaster.save_model()
        forecaster.plot_results(df, X, y, dates)
        
        # Get product name
        product = Product.objects.get(id=product_id)
        
        return {
            'product_id': product_id,
            'product_name': product.name,
            'model_type': model_type,
            'best_params': forecaster.best_params,
            'metrics': metrics,
            'data_points': len(df),
            'window_size': window_size,
            'model_path': forecaster.model_path,
            'plot_path': forecaster.plot_path
        }
        
    except Exception as e:
        return {
            'product_id': product_id,
            'error': str(e)
        }

def train_all_products(model_type='random_forest', days=365, window_size=30, optimize=False):
    """
    Train models for all products with sufficient data
    Args:
        model_type: Type of model to use
        days: Number of days of historical data to use
        window_size: Number of previous days to use as features
        optimize: Whether to perform hyperparameter optimization
    Returns:
        List of training results for all products
    """
    results = []
    products = Product.objects.all()
    
    for product in products:
        try:
            result = train_product_model(
                product.id,
                model_type=model_type,
                days=days,
                window_size=window_size,
                optimize=optimize
            )
            results.append(result)
        except Exception as e:
            results.append({
                'product_id': product.id,
                'product_name': product.name,
                'error': str(e)
            })
    
    return results

if __name__ == '__main__':
    # Example usage
    import django
    django.setup()
    
    # Train model for a specific product
    print("Training model for product 1...")
    result = train_product_model(1)
    print(result)
    
    # Train models for all products
    # print("Training models for all products...")
    # results = train_all_products()
    # for r in results:
    #     print(r)