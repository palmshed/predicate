import time
from typing import Optional
from contextlib import contextmanager
from app.observability.logging import get_logger

logger = get_logger("trace")


class TraceContext:
    __slots__ = ("request_id", "tenant_id", "spans", "_start")

    def __init__(self, request_id: str, tenant_id: Optional[str] = None):
        self.request_id = request_id
        self.tenant_id = tenant_id
        self.spans = []
        self._start = time.perf_counter()

    def add_span(self, name: str, duration_ms: float, **extra):
        span = {"name": name, "ms": round(duration_ms, 2), **extra}
        self.spans.append(span)
        logger.info(
            f"span:{name}",
            extra={"route": name, "duration_ms": round(duration_ms, 2), **extra}
        )

    @contextmanager
    def span(self, name: str, **extra):
        start = time.perf_counter()
        try:
            yield
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            self.add_span(name, duration, error=str(e), **extra)
            raise
        else:
            duration = (time.perf_counter() - start) * 1000
            self.add_span(name, duration, **extra)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "total_ms": self.total_ms,
            "spans": self.spans,
        }


@contextmanager
def trace_span(name: str, **extra):
    start = time.perf_counter()
    try:
        yield
    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        logger.info(f"span:{name}", extra={"duration_ms": round(duration, 2), "error": str(e), **extra})
        raise
    else:
        duration = (time.perf_counter() - start) * 1000
        logger.info(f"span:{name}", extra={"duration_ms": round(duration, 2), **extra})
