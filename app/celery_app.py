"""Celery instance. Broker/back-end = Redis. Rendering stays single-threaded (TZ §4):
run the worker with --concurrency=1. Set CELERY_TASK_ALWAYS_EAGER=1 for local dev without Redis.
"""
from celery import Celery
from config import Config

celery = Celery(
    "videobot",
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery.conf.update(
    task_always_eager=Config.CELERY_TASK_ALWAYS_EAGER,
    task_track_started=True,
    worker_concurrency=1,          # hard single-thread; also pass --concurrency=1
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    result_expires=3600,
    task_default_queue="videobot",
)
