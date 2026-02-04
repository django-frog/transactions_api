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

## 🛠️ Data Pre-processing: Temporal Sorting

A critical architectural decision was made to **pre-sort the input CSV by timestamp** before ingestion. 

### Why Sorting is Mandatory:
* **Monotonic Virtual Clock:** The system uses a "Virtual Clock" derived from transaction timestamps to determine archival boundaries. If data were processed out of order, the clock could jump forward, causing valid "recent" transactions to be incorrectly flagged as historical.

* **Deterministic Archival:** Sorting ensures that the 7-day "Hot Data" window moves forward consistently. 


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
    git clone https://github.com/django-frog/transactions_api.git
    cd transactions_api
    ```

2. **Configure Environment Variables**

    The application is configured entirely via a single .env file. Create this file in the project root.

    > **No YAML file is required anymore.**

    An example file is provided:

    ```bash
    cp .env.example .env
    ```

    Ensure your .env contains the following: 

    ```env
    # --- Infrastructure ---
    REDIS_HOST=redis
    REDIS_PORT=6379
    REDIS_PASSWORD=
    
    MONGODB_URI=mongodb://mongo:27017
    MONGODB_DATABASE=fintech_db
    MONGODB_COLLECTION=daily_stats
    
    # --- Application Settings ---
    CSV_PATH=app/transactions_1_month.csv
    BATCH_SIZE=50
    RETENTION_DAYS=7
    
    # --- Logging & Verbosity ---
    # Options: DEBUG (detailed), INFO (clean summary), WARNING, ERROR
    LOG_LEVEL=INFO
    ```

    > **Note:** If running via Docker Compose, use the service names redis and mongo as hostnames


3.  **Start the services:**
    
    The system uses Docker Compose to orchestrate the API, Redis, and MongoDB.
    
    ```bash
    docker compose up --build
    ```
 
     > **Note:**
    This project uses Docker Compose v2 (docker compose), not the legacy docker-compose binary.
 

    This will start:
    * Redis
    * MongoDB
    * FastAPI application (including background workers).



4.  **Access the API:**
    * **Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
    * **Stats Endpoint:** `GET /stats?from_date=2026-01-01&to_date=2026-01-30`

    * **API Response Format:**

        The /stats endpoint returns a nested JSON object:
        ```json
        {
          "data": {
            "2026-01-01": {
              "deposits": {
                "paypal": 343.4,
                "crypto": 893,
                "wire": 234
              },
              "withdrawals": {
                "visa": 342,
                "crypto": 475,
                "wire": 879
              }
            },
            "2026-01-02": {
              "deposits": {
                "visa": 53.4,
                "crypto": 893,
                "wire": 234
              },
              "withdrawals": {
                "paypal": 50,
                "visa": 475,
                "wire": 879,
                "crypto": 948
              }
            }
          }
        }

## 🔍 Logging and Monitoring
The application uses Python's standard logging module for observability, configured via `LOG_LEVEL` in .env (options: DEBUG, INFO, WARNING, ERROR; default INFO).

- **Verbosity Balance**: At INFO level, logs focus on key events (e.g., "Imported X transactions," "Aggregated to day Y," "Dumped Z days with W aggregates to MongoDB") without per-transaction spam—ensuring the terminal is informative during startup/operation but not overwhelming.
- **Outputs**: Logs to console (visible in Docker) and a mounted volume (/logs/app.log for persistence).
- **Error Handling**: Errors (e.g., invalid CSV rows) are logged and skipped to maintain uptime; critical failures halt the worker with traceback.

For production, integrate with tools like ELK or Prometheus—here, kept simple per task scope.

