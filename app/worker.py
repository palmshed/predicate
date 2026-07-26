import csv
import io
import os

from celery import Celery

from app.compiler.sql_builder import build_secure_query
from app.database.connection import execute_secure_query

celery_worker = Celery(
    "predicate_tasks",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)


@celery_worker.task(bind=True)
def execute_heavy_export_task(self, blueprint_dict: dict, tenant_id: str) -> dict:
    self.update_state(state="PROCESSING", meta={"progress": 10})

    try:
        blueprint_dict.setdefault("pagination", {})["limit"] = 10000

        sql_string, query_parameters = build_secure_query(blueprint_dict, tenant_id=tenant_id)
        self.update_state(state="PROCESSING", meta={"progress": 40})

        db_results, _db_ms = execute_secure_query(sql_string, query_parameters)
        self.update_state(state="PROCESSING", meta={"progress": 70})

        if not db_results:
            return {"status": "completed", "rows_exported": 0, "csv_payload": ""}

        csv_buffer = io.StringIO()
        csv_writer = csv.DictWriter(csv_buffer, fieldnames=list(db_results[0].keys()))

        csv_writer.writeheader()
        csv_writer.writerows(db_results)

        return {
            "status": "completed",
            "rows_exported": len(db_results),
            "csv_payload": csv_buffer.getvalue(),
        }

    except Exception as e:
        self.update_state(state="FAILED", meta={"error": str(e)})
        raise e
