FROM python:3.12-slim
WORKDIR /app
COPY dashboard/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY dashboard /app/dashboard
ENV DASHBOARD_DB=/data/research.sqlite3 PYTHONUNBUFFERED=1
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 60 dashboard.server:application"]
