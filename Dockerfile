FROM python:3.11-slim

WORKDIR /app

# Install curl for docker healthcheck and postgres client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies for API and Celesto ledger
RUN pip install --no-cache-dir \
    fastapi==0.115.5 \
    uvicorn==0.32.1 \
    pydantic==2.10.2 \
    psycopg2-binary==2.9.10 \
    httpx==0.28.0

# Copy application source code, seeds, reports, and logs
COPY src/ /app/src/
COPY seeds/ /app/seeds/
COPY reports/ /app/reports/
COPY logs/ /app/logs/
COPY demo/ /app/demo/

ENV PYTHONPATH=/app
ENV API_PORT=8080
ENV DATABASE_URL=postgresql://ledger:ledger@ledger:5432/ledger

EXPOSE 8080

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
