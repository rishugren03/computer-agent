FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install dependencies including existing requirements and new message queue dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir redis taskiq taskiq-redis

# Copy all source files
COPY . .

# Default command to run the worker listener
CMD ["taskiq", "worker", "worker:broker", "--workers", "1"]
