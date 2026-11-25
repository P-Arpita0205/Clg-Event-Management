FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install --no-install-recommends -y default-libmysqlclient-dev gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "run:app"]
