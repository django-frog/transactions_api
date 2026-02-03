FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application and data
COPY app ./app
COPY app/settings.yaml /app/settings.yaml

# Copy and prepare the entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Environment setup
ENV PYTHONPATH=/app

EXPOSE 8000

# Use the entrypoint to run sorting BEFORE the app starts
ENTRYPOINT ["/app/entrypoint.sh"]