FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-hindsight.txt ./
RUN python -m pip install --no-cache-dir -r requirements-hindsight.txt

COPY . .
RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/.runtime \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
