"""Gunicorn configuration for production deployment."""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
