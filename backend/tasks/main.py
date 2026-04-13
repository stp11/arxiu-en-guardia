import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "en-guardia",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.episode_tasks", "tasks.backup_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Madrid",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

celery_app.conf.beat_schedule = {
    "ingest-and-classify-weekly": {
        "task": "tasks.episode_tasks.ingest_and_classify_chain",
        "schedule": crontab(
            day_of_week=[0, 6],
            hour=17,
            minute=0,
        ),
        "kwargs": {
            "batch_size": 1,
            "max_total": 1,
        },
    },
    "backup-database-weekly": {
        "task": "tasks.backup_tasks.backup_database",
        "schedule": crontab(
            day_of_week=0,
            hour=20,
            minute=0,
        ),
    },
}
