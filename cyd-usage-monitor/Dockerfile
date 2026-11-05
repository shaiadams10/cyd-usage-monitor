FROM python:3.15.0-slim-bookworm
WORKDIR /app
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY server/wakeup_report.py /app/wakeup_report.py
COPY server/server.py server/collector.py server/storage.py server/diagnostics.py server/wakeups.py server/wakeup_cli.py server/wakeup_codex.py server/wakeup_catalog.py server/dashboard.html /app/
COPY server/static /app/static
COPY instructions/FLASHING_GUIDE.md /app/flashing-guide.md
EXPOSE 8000
CMD ["python3", "/app/server.py"]
