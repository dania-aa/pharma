FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY ../../database/schema.sql /app/../../database/schema.sql 2>/dev/null || true

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "main.py"]
CMD ["--max-trials", "10000"]
