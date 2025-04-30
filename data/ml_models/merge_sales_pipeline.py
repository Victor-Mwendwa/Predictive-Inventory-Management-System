# merge_sales_pipeline.py

from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import time

# Connect to MongoDB
client = MongoClient("mongodb://root:example@localhost:27017/")
db = client["kyoskdata"]

# Aggregation pipeline to merge data from multiple collections
pipeline = [
    {"$unwind": "$items"},
    {"$limit": 100},
    {"$lookup": {
        "from": "projectedQuantities",
        "let": {"item_code": "$items.catalogItemId", "territory": "$territoryId"},
        "pipeline": [
            {"$match": {
                "$expr": {
                    "$and": [
                        {"$eq": ["$itemCode", "$$item_code"]},
                        {"$eq": ["$territoryId", "$$territory"]}
                    ]
                }
            }}
        ],
        "as": "projected_data"
    }},
    {"$unwind": {"path": "$projected_data", "preserveNullAndEmptyArrays": True}},
    {"$lookup": {
        "from": "markets",
        "localField": "territoryId",
        "foreignField": "market_id",
        "as": "market"
    }},
    {"$unwind": {"path": "$market", "preserveNullAndEmptyArrays": True}},
    {"$lookup": {
        "from": "outlets",
        "localField": "outletId",
        "foreignField": "outlet_id",
        "as": "outlet"
    }},
    {"$unwind": {"path": "$outlet", "preserveNullAndEmptyArrays": True}},
    {"$lookup": {
        "from": "retailers",
        "localField": "retailerId",
        "foreignField": "retailer_id",
        "as": "retailer"
    }},
    {"$unwind": {"path": "$retailer", "preserveNullAndEmptyArrays": True}},
    {"$addFields": {
        "currency_rate": {
            "$switch": {
                "branches": [
                    {"case": {"$eq": ["$currency", "KES"]}, "then": 1},
                    {"case": {"$eq": ["$currency", "TZS"]}, "then": 0.057},
                    {"case": {"$eq": ["$currency", "UGX"]}, "then": 0.039},
                    {"case": {"$eq": ["$currency", "NGN"]}, "then": 0.29},
                ],
                "default": 1
            }
        },
    }},
    {"$addFields": {
        "normalizedTotalAmount": {"$multiply": ["$totalAmount", "$currency_rate"]}
    }},
    {"$project": {
        "_id": 0,
        "orderId": "$id",
        "createdDate": 1,
        "territoryId": 1,
        "catalogItemId": "$items.catalogItemId",
        "catalogItemQty": "$items.catalogItemQty",
        "sellingPrice": "$items.sellingPrice",
        "projectedQty": "$projected_data.projectedQty",
        "binQty": "$projected_data.binQty",
        "market_name": "$market.name",
        "outlet_name": "$outlet.name",
        "retailer_name": "$retailer.first_name",
        "retailer_email": "$retailer.email",
        "currency": 1,
        "totalAmount": 1,
        "normalizedTotalAmount": 1
    }}
]

# Run aggregation and stream results
cursor = db.salesOrders.aggregate(pipeline, allowDiskUse=True)
merged_collection = db["mergedSalesData"]

batch = []
batch_size = 10000
processed = 0
start_time = time.time()
total_docs = db.salesOrders.estimated_document_count()

for doc in cursor:
    batch.append(doc)
    processed += 1

    if len(batch) == batch_size:
        try:
            merged_collection.insert_many(batch, ordered=False)
            elapsed = time.time() - start_time
            print(f"✅ Inserted {processed} documents | {processed / total_docs * 100:.2f}% done | Elapsed: {elapsed:.2f}s")
        except BulkWriteError as bwe:
            print("⚠️ Bulk insert error:", bwe.details)
        batch = []

if batch:
    try:
        merged_collection.insert_many(batch, ordered=False)
        elapsed = time.time() - start_time
        print(f"✅ Final insert complete: {processed} documents total | Total time: {elapsed:.2f} sec")
    except BulkWriteError as bwe:
        print("⚠️ Final batch insert error:", bwe.details)

print("🎯 Merge complete. Data written to 'mergedSalesData'.")
