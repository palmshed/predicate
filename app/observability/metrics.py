import os
import resource
import threading
import time

from app.observability.logging import get_logger

logger = get_logger("metrics")


class _MetricsStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}
        self._started_at = time.time()

    def inc(self, name: str, value: int = 1):
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def dec(self, name: str, value: int = 1):
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) - value

    def observe(self, name: str, value: float):
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            if len(self._histograms[name]) > 10000:
                self._histograms[name] = self._histograms[name][-5000:]

    def gauge(self, name: str, value: float):
        with self._lock:
            self._gauges[name] = value

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def get_histogram(self, name: str) -> dict[str, float]:
        with self._lock:
            vals = self._histograms.get(name, [])
        if not vals:
            return {
                "count": 0,
                "sum": 0,
                "min": 0,
                "avg": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
                "max": 0,
            }
        sorted_vals = sorted(vals)
        count = len(sorted_vals)
        return {
            "count": count,
            "sum": round(sum(sorted_vals), 2),
            "min": round(sorted_vals[0], 2),
            "avg": round(sum(sorted_vals) / count, 2),
            "p50": round(sorted_vals[int(count * 0.5)], 2),
            "p95": round(sorted_vals[int(count * 0.95)], 2),
            "p99": round(sorted_vals[int(count * 0.99)], 2),
            "max": round(sorted_vals[-1], 2),
        }

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0)

    def to_prometheus(self) -> str:
        lines = []
        uptime = round(time.time() - self._started_at, 0)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = round(usage.ru_maxrss / 1024, 1)

        lines.append("# TYPE predicate_uptime_seconds gauge")
        lines.append(f"predicate_uptime_seconds {uptime}")
        lines.append("# TYPE predicate_process_rss_mb gauge")
        lines.append(f"predicate_process_rss_mb {rss_mb}")
        lines.append("# TYPE predicate_process_pid gauge")
        lines.append(f"predicate_process_pid {os.getpid()}")

        with self._lock:
            counters = dict(self._counters)
            histograms = dict(self._histograms)
            gauges = dict(self._gauges)

        for name, val in counters.items():
            safe = name.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE predicate_{safe} counter")
            lines.append(f"predicate_{safe} {val}")

        for name, val in gauges.items():
            safe = name.replace(".", "_").replace("-", "_")
            lines.append(f"# TYPE predicate_{safe} gauge")
            lines.append(f"predicate_{safe} {val}")

        for name, vals in histograms.items():
            safe = name.replace(".", "_").replace("-", "_")
            if not vals:
                continue
            sorted_vals = sorted(vals)
            count = len(sorted_vals)
            lines.append(f"# TYPE predicate_{safe} summary")
            lines.append(f'predicate_{safe}{{quantile="0.5"}} {sorted_vals[int(count * 0.5)]:.2f}')
            lines.append(
                f'predicate_{safe}{{quantile="0.95"}} {sorted_vals[int(count * 0.95)]:.2f}'
            )
            lines.append(
                f'predicate_{safe}{{quantile="0.99"}} {sorted_vals[int(count * 0.99)]:.2f}'
            )
            lines.append(f"predicate_{safe}_sum {sum(sorted_vals):.2f}")
            lines.append(f"predicate_{safe}_count {count}")

        return "\n".join(lines) + "\n"


metrics = _MetricsStore()


class PrometheusExporter:
    def __init__(self, store: _MetricsStore):
        self._store = store

    def export(self) -> str:
        return self._store.to_prometheus()
