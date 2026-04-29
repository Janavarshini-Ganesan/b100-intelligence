import os
import sys
import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Add project root so ETL scripts are importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ETL_DIR = os.path.join(PROJECT_ROOT, "etl")


def run_script(script_name):
    """Run an ETL script and return success/failure."""
    import subprocess
    script_path = os.path.join(ETL_DIR, script_name)
    python_exe  = sys.executable

    logger.info(f"Running {script_name}...")
    result = subprocess.run(
        [python_exe, script_path],
        capture_output=True, text=True, timeout=600
    )

    if result.returncode == 0:
        logger.info(f"✅ {script_name} completed")
        return {"status": "success", "script": script_name, "output": result.stdout[-500:]}
    else:
        logger.error(f"❌ {script_name} failed: {result.stderr[-300:]}")
        return {"status": "failed",  "script": script_name, "error":  result.stderr[-300:]}


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_full_etl(self):
    """Run all 3 ETL scripts: Extract → Clean → Load."""
    try:
        results = []
        for script in [
            "01_extract_from_excel.py",
            "02_clean_and_transform.py",
            "03_load_to_warehouse.py",
        ]:
            result = run_script(script)
            results.append(result)
            if result["status"] == "failed":
                raise Exception(f"{script} failed")

        # Clear Redis cache so fresh data is served
        cache.clear()
        logger.info("✅ Full ETL complete — Redis cache cleared")
        return {"status": "success", "steps": results}

    except Exception as exc:
        logger.error(f"ETL pipeline failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_ml_scoring(self):
    """Run ML scoring script after ETL."""
    try:
        result = run_script("04_ml_scoring.py")
        if result["status"] == "failed":
            raise Exception("ML scoring failed")

        cache.delete("scores__")
        cache.delete("dashboard_summary")
        logger.info("✅ ML scoring complete — score cache cleared")
        return result

    except Exception as exc:
        logger.error(f"ML scoring failed: {exc}")
        raise self.retry(exc=exc)


@shared_task
def health_check():
    """Ping DB and Redis every 30 min — log if down."""
    from django.db import connection
    errors = []

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dim_company")
            count = cur.fetchone()[0]
        logger.info(f"✅ DB healthy — {count} companies")
    except Exception as e:
        errors.append(f"DB error: {e}")
        logger.error(f"❌ DB health check failed: {e}")

    try:
        cache.set("ping", "pong", 10)
        assert cache.get("ping") == "pong"
        logger.info("✅ Redis healthy")
    except Exception as e:
        errors.append(f"Redis error: {e}")
        logger.error(f"❌ Redis health check failed: {e}")

    return {"errors": errors} if errors else {"status": "all healthy"}
