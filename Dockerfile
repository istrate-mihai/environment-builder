# Image for the config validator (Python + PyYAML only).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY validator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY validator/validate.py validator/server.py validator/supported.yml ./

# Run as a non-root user; /config is mounted read-only, /output receives generated files
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /config /output \
    && chown appuser /output
USER appuser

ENTRYPOINT ["python", "validate.py"]
CMD ["--config", "/config/environment.yml", "--out-dir", "/output"]
