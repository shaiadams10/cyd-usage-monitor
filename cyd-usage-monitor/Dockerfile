FROM python:3.11.15-slim-bookworm
WORKDIR /app
COPY server/server.py server/collector.py server/storage.py server/dashboard.html /app/
COPY server/static /app/static
EXPOSE 8000
CMD ["python3", "/app/server.py"]
