from datetime import timedelta

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pymongo import MongoClient
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import os


# MongoDB connection
client = MongoClient("mongodb://root:example@localhost:27017/")
db = client["kyoskdata"]
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATIC_DIR = os.path.join(PROJECT_ROOT, 'static', 'forecasts')
os.makedirs(STATIC_DIR, exist_ok=True)


# Load merged sales data
print("📥 Loading data from MongoDB 'mergedSalesData' collection...")
cursor = db["mergedSalesData"].find({}, {"_id": 0})
data = pd.DataFrame(list(cursor))
print(f"✅ Loaded {len(data):,} records")

# Preprocess dates
data['createdDate'] = pd.to_datetime(data['createdDate'])
data['date'] = data['createdDate'].dt.date
aggregated = data.groupby(["date", "territoryId", "catalogItemId"]).agg({
    "catalogItemQty": "sum",
    "normalizedTotalAmount": "sum"
}).reset_index()

# Encode categorical variables
le_territory = LabelEncoder()
le_item = LabelEncoder()
aggregated['territory_encoded'] = le_territory.fit_transform(aggregated['territoryId'])
aggregated['item_encoded'] = le_item.fit_transform(aggregated['catalogItemId'])
aggregated['dayofyear'] = pd.to_datetime(aggregated['date']).dt.dayofyear

# Prepare features and target
X = aggregated[['territory_encoded', 'item_encoded', 'dayofyear']]
y = aggregated['catalogItemQty']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train LightGBM model
model = lgb.LGBMRegressor()
model.fit(X_train, y_train)

# Predict and evaluate
y_pred = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print(f"\n📈 LightGBM RMSE: {rmse:.2f}")
print(f"📈 LightGBM R² Score: {r2:.2f}")

# Save CSV of aggregated data
csv_path = "daily_demand_training_data.csv"
aggregated.to_csv(csv_path, index=False)
print(f"📦 Exported training data to {csv_path}")

# Save feature importance plot
fig, ax = plt.subplots(figsize=(10, 6))
lgb.plot_importance(model, max_num_features=10, importance_type='gain', ax=ax)
plt.title("Feature Importance")
plt.tight_layout()
importance_path = "feature_importance.png"
plt.savefig(importance_path)
print(f"📸 Saved feature importance plot to {importance_path}")

# --------------------------------------------
# 🔮 Forecast next 7 days per item/territory
# --------------------------------------------
print("\n🔮 Forecasting next 7 days of demand...")
last_date = aggregated['date'].max()
territories = aggregated['territoryId'].unique()
items = aggregated['catalogItemId'].unique()

future_dates = [last_date + timedelta(days=i) for i in range(1, 8)]
future_rows = []

for territory in territories:
    for item in items:
        for date in future_dates:
            future_rows.append({
                "territoryId": territory,
                "catalogItemId": item,
                "territory_encoded": le_territory.transform([territory])[0] if territory in le_territory.classes_ else -1,
                "item_encoded": le_item.transform([item])[0] if item in le_item.classes_ else -1,
                "dayofyear": date.timetuple().tm_yday,
                "forecast_date": date
            })

future_df = pd.DataFrame(future_rows)

# Filter valid encodings only
future_df = future_df[(future_df['territory_encoded'] >= 0) & (future_df['item_encoded'] >= 0)]

# Predict future demand
X_future = future_df[['territory_encoded', 'item_encoded', 'dayofyear']]
future_df['forecastedQty'] = model.predict(X_future)

# Ensure forecast directory exists
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATIC_DIR = os.path.join(PROJECT_ROOT, 'static', 'forecasts')
os.makedirs(STATIC_DIR, exist_ok=True)

# Save aggregated training data
csv_path = os.path.join(STATIC_DIR, "daily_demand_training_data.csv")
aggregated.to_csv(csv_path, index=False)
print(f"📦 Exported training data to {csv_path}")

# Save feature importance plot
fig, ax = plt.subplots(figsize=(10, 6))
lgb.plot_importance(model, max_num_features=10, importance_type='gain', ax=ax)
plt.title("Feature Importance")
plt.tight_layout()
importance_path = os.path.join(STATIC_DIR, "feature_importance.png")
plt.savefig(importance_path)
print(f"📸 Saved feature importance plot to {importance_path}")

# Save forecast results to CSV
forecast_path = os.path.join(STATIC_DIR, "forecast_7_day_results.csv")
future_df.to_csv(forecast_path, index=False)
print(f"📦 Saved 7-day forecast results to {forecast_path}")

# Save forecast results to MongoDB
future_df['forecast_date'] = pd.to_datetime(future_df['forecast_date'])
db["forecastResults"].delete_many({})
db["forecastResults"].insert_many(future_df.to_dict("records"))
print("✅ Forecast results saved to MongoDB 'forecastResults' collection.")