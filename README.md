# 🏦 Transaction Aggregation Service

A high-performance asynchronous backend service that ingests, aggregates, and archives financial transaction data. Built with **FastAPI**, **Redis**, and **MongoDB**.

![System Diagram](task_workflow.drawio.png)

## 🚀 Overview

This system allows for the ingestion of high-throughput transaction data via CSV, real-time aggregation in Redis, and long-term archival in MongoDB. It exposes a unified HTTP API that seamlessly merges "hot" (recent) and "cold" (historical) data.

### Key Features
* **Event-Driven Ingestion:** Transactions are processed asynchronously via Redis Streams to prevent blocking the API.
* **Hybrid Storage Architecture:**
    * **Redis:** Serves as the write-heavy buffer and read cache for the last 7 days.
    * **MongoDB:** Serves as the immutable source of truth for historical data.
* **Virtual Clock Simulation:** The system respects the timestamps in the CSV data to simulate "replay" behavior, ensuring accurate archival boundaries regardless of when the script is run.
* **Atomic Data Migration:** The `Persistor` worker uses an "Upsert -> Confirm -> Delete" strategy to ensure zero data loss during the migration from Redis to MongoDB.

## 🛠️ Tech Stack
* **Language:** Python 3.10+
* **Framework:** FastAPI (fully async)
* **Cache/Queue:** Redis (Streams for queuing, Hashes for aggregation)
* **Database:** MongoDB (Motor async driver)
* **Containerization:** Docker & Docker Compose

## 🏗️ Architecture

### 1. The Components
The application runs three concurrent background tasks managed by the FastAPI Lifespan:

1.  **Importer (`CsvTransactionImporter`):** Reads the CSV file, respects the `sleep_ms` delay, and pushes raw events to a Redis Stream (`transactions`).
2.  **Aggregator (`RedisAggregationWorker`):** Consumes the stream, updates daily aggregates in Redis Hashes, and advances the "Virtual Clock."
3.  **Persistor (`MongoPersistenceWorker`):** Wakes up every 10 seconds. Checks the "Virtual Clock" and moves any data older than 7 days from Redis to MongoDB using atomic operations.

### 2. Redis Key Design
To optimize for $O(1)$ access and simple atomic increments, we use the following key schema:

* **Aggregation:** `agg:{date}:{type}` (Hash)
    * *Example:* `agg:2026-01-01:deposit`
    * *Fields:* `paypal`, `visa`, `wire`
    * *Values:* Total float amount
* **Discovery:**
    * `system:tracked_days` (Set): A registry of all days currently living in Redis. Used by the Persistor to know what to scan.
    * `system:virtual_clock` (String): The timestamp of the latest processed transaction.

## 🏃‍♂️ How to Run

### Prerequisites
* Docker & Docker Compose

### Steps
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/django-frog/transactions_api.git](https://github.com/django-frog/transactions_api.git)
    cd transactions_api
    ```

2.  **Start the services:**
    ```bash
    docker-compose up --build
    ```
    *This will start Redis, MongoDB, and the FastAPI application.*

3.  **Access the API:**
    * **Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
    * **Stats Endpoint:** `GET /stats?from_date=2026-01-01&to_date=2026-01-30`

## 🧪 Implementation Details & Trade-offs

* **Floating Point Math:** The requirements specified `amount` as a float. In a real-world production Fintech environment, `Decimal` or integer-based cents would be used to strictly avoid IEEE 754 precision errors.
* **Concurrency:** The system explicitly yields control (`await asyncio.sleep(0.01)`) inside heavy loops to prevent CPU starvation and ensure all background workers get fair access to the event loop.
* **Idempotency:** The MongoDB persistence uses `$inc` (increment) logic. This allows the system to be restarted or replay data without "resetting" historical totals; it will simply add to them.