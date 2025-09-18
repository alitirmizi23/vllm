# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install runtime dependencies for the proxy server.
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx prometheus-client

# Copy only the pieces required to run the proxy.
COPY tools/metrics_proxy /app/tools/metrics_proxy
COPY vllm /app/vllm

EXPOSE 8000

ENTRYPOINT ["python", "-m", "tools.metrics_proxy.proxy_server"]
