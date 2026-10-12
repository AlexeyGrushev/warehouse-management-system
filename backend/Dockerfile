FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app/src

EXPOSE 8000
# Миграции применяются при старте, если они уже есть в проекте
CMD ["sh", "-c", "if [ -f alembic.ini ]; then alembic upgrade head; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
