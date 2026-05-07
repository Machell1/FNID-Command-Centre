FROM python:3.9-slim AS base

RUN groupadd -r fnid && useradd -r -g fnid -d /app fnid

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fnid_portal/ fnid_portal/
COPY wsgi.py gunicorn.conf.py ./

RUN mkdir -p /app/data && chown -R fnid:fnid /app

USER fnid

ENV FLASK_ENV=production
ENV FNID_DB_PATH=/app/data/fnid.db
ENV FNID_UPLOAD_DIR=/app/data/uploads
ENV FNID_EXPORT_DIR=/app/data/exports

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/login')" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
