FROM python:3.14.0-slim-bookworm
WORKDIR /app
COPY server/server.py server/collector.py server/storage.py server/dashboard.html /app/
COPY server/static /app/static
COPY instructions/FLASHING_GUIDE.md /app/flashing-guide.md
EXPOSE 8000
CMD ["python3", "/app/server.py"]
