FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /code/app

# Папка для файла SQLite (монтируется как volume).
RUN mkdir -p /data

EXPOSE 8000

# --proxy-headers + доверие к X-Forwarded-* от nginx (правильная схема https в куках/ссылках)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
