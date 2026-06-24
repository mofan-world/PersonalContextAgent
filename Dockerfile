FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PCA_DB_PATH=/data/personal_context.sqlite3

WORKDIR /app

COPY app ./app
COPY static ./static

EXPOSE 8088

CMD ["python", "-m", "app.main"]
