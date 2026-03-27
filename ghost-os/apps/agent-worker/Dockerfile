FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install dependencies including existing requirements and new message queue dependencies
RUN apt-get update && apt-get install -y nodejs npm python3-venv python3.10-venv && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir redis taskiq taskiq-redis
RUN patchright install chromium

# Copy all source files
COPY . .

# Default command to run the worker listener
CMD ["taskiq", "worker", "worker:broker", "--workers", "1"]
