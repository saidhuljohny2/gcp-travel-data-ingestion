FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src ./src

USER app
EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn --bind :${PORT:-8080} --workers 2 --threads 8 --timeout 0 app:app"]
