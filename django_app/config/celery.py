import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("b100")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ── Scheduled Tasks ──────────────────────────────────────────
app.conf.beat_schedule = {

    # Full ETL pipeline — every day at midnight IST
    "full-etl-midnight": {
        "task": "api.tasks.run_full_etl",
        "schedule": crontab(hour=0, minute=0),
    },

    # ML scoring — every day at 1 AM IST (after ETL finishes)
    "ml-scoring-1am": {
        "task": "api.tasks.run_ml_scoring",
        "schedule": crontab(hour=1, minute=0),
    },

    # Health check ping — every 30 minutes
    "health-check": {
        "task": "api.tasks.health_check",
        "schedule": crontab(minute="*/30"),
    },
}

app.conf.timezone = "Asia/Kolkata"
