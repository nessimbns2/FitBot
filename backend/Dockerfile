# Backend Dockerfile for FitBot Coach
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements_v2.txt .
RUN pip install --no-cache-dir -r requirements_v2.txt


# Copy backend source code
COPY . .

# Expose API port
EXPOSE 8000

# Run entrypoint
CMD ["uvicorn", "main_v2:app", "--host", "0.0.0.0", "--port", "8000"]
