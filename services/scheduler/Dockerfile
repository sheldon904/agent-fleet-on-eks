FROM python:3.11-slim

WORKDIR /app
COPY app.py .

RUN useradd -u 10001 -m appuser
USER 10001

ENV PORT=8080 \
    POLL_INTERVAL=5 \
    PYTHONUNBUFFERED=1

EXPOSE 8080
ENTRYPOINT ["python", "-u", "app.py"]
