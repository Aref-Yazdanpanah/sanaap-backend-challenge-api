FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/ requirements/
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements/local.txt
COPY . .
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
