FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY ai_monitor/requirements.txt /app/ai_monitor/requirements.txt
RUN pip install --no-cache-dir -r /app/ai_monitor/requirements.txt

# Copy source code
COPY . /app/

# Create directories
RUN mkdir -p /app/ai_monitor/store /app/ai_monitor/generated_reports /app/ai_monitor/generated_ppts

EXPOSE 8081

CMD ["uvicorn", "ai_monitor.main:app", "--host", "0.0.0.0", "--port", "8081"]
