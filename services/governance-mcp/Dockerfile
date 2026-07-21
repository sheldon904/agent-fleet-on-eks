FROM python:3.11-slim

WORKDIR /app
COPY app.py .

# Non-root user + a writable volume mount point for the audit log.
RUN useradd -u 10001 -m appuser && mkdir -p /data && chown appuser /data
USER 10001

ENV AUDIT_LOG_PATH=/data/audit.log \
    PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
ENTRYPOINT ["python", "-u", "app.py"]
