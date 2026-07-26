import os
import sys
import json
import logging
import contextvars
from datetime import datetime, timezone
from typing import Optional

request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
tenant_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("tenant_id", default=None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        req_id = request_id_var.get()
        if req_id:
            log_entry["request_id"] = req_id

        tid = tenant_id_var.get()
        if tid:
            log_entry["tenant_id"] = tid

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        for key in ("route", "method", "status_code", "duration_ms",
                     "compile_ms", "validate_ms", "execute_ms",
                     "cache_hit", "rows", "target_table", "error_code"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json")

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"predicate.{name}")
