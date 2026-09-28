FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-hindsight.txt ./
RUN python -m pip install --no-cache-dir -r requirements-hindsight.txt

COPY . .
RUN mkdir -p /app/.runtime

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
