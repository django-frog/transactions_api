#!/bin/bash
set -e

# 1. Run the sorting pre-processor
echo "Starting pre-processing: Sorting transactions..."
python app/scripts/pre_processing.py

# 2. Start the application
echo "Pre-processing complete. Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000