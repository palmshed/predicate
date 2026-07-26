#!/usr/bin/env python3
"""
Predicate Performance Benchmark Suite

Four phases:
  1. Compiler — schema complexity scaling (10–500 tables)
  2. Database — query execution against real datasets
  3. Load    — concurrent HTTP requests through the full pipeline
  4. Failure — graceful degradation under fault conditions

Usage:
  python benchmark.py                    # all phases
  python benchmark.py --phase 1          # compiler only
  python benchmark.py --phase 3 --users 100 --duration 30
  python benchmark.py --phase 2 --dataset large
"""

import argparse
import json
import os
import random
import statistics
import sys
import time
import threading
import concurrent.futures
from typing import Any, Dict, List, Optional, Tuple

# ── Bootstrap ────────────────────────────────────────────────────────────
os.environ.setdefault("REQUIRE_AUTH", "false")
os.environ.setdefault("LLM_PROVIDER", "openrouter")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _percentiles(data: List[float]) -> Dict[str, float]:
    s = sorted(data)
    n = len(s)
    if n == 0:
        return {"min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "avg": 0}
    return {
        "min": round(s[0], 2),
        "p50": round(s[n // 2], 2),
        "p95": round(s[int(n * 0.95)], 2),
        "p99": round(s[int(n * 0.99)], 2),
        "max": round(s[-1], 2),
        "avg": round(statistics.mean(s), 2),
    }


def _format_ms(ms: float) -> str:
    if ms < 1:
        return f"{ms*1000:.0f}us"
    return f"{ms:.2f}ms"


def _print_header(title: str):
    w = 70
    print(f"\n{'━' * w}")
    print(f"  {title}")
    print(f"{'━' * w}")


def _print_row(label: str, values: Dict[str, str]):
    parts = [f"{k}: {v}" for k, v in values.items()]
    print(f"  {label:<20s} {' | '.join(parts)}")


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1: COMPILER
# ══════════════════════════════════════════════════════════════════════════

def _generate_schema(num_tables: int) -> Tuple[Dict, Dict]:
    """Generate ALLOWED_SCHEMA and RELATIONSHIP_GRAPH for N tables."""
    schema = {}
    relationships = {}
    table_names = [f"table_{i}" for i in range(num_tables)]

    for i, name in enumerate(table_names):
        cols = {"id", "name", "tenant_id"}
        if i > 0:
            cols.add(f"fk_table_{i-1}_id")
        schema[name] = cols

    for i in range(1, num_tables):
        relationships[(table_names[i], table_names[i-1])] = (
            f"{table_names[i]}.fk_table_{i-1}_id = {table_names[i-1]}.id"
        )
        relationships[(table_names[i-1], table_names[i])] = (
            f"{table_names[i-1]}.id = {table_names[i]}.fk_table_{i-1}_id"
        )

    return schema, relationships


def _make_blueprints(schema: Dict, relationships: Dict, count: int = 10) -> List[Dict]:
    """Generate valid blueprints against a given schema."""
    tables = list(schema.keys())
    blueprints = []

    for i in range(count):
        target = tables[i % len(tables)]
        cols = list(schema[target] - {"id", "tenant_id"})

        bp: Dict[str, Any] = {
            "target_table": target,
            "projection_columns": cols[:2] if cols else [],
            "filters": [],
            "sorting": {"column": cols[0] if cols else "id", "direction": "asc"},
            "pagination": {"limit": 20, "offset": 0},
        }
        blueprints.append(bp)

    return blueprints


def phase1_compiler(iterations: int = 5000, warmup: int = 500):
    """Benchmark SQL compilation across schema complexities."""
    import app.compiler.sql_builder as sqlb

    _print_header("PHASE 1: COMPILER — Schema Complexity Scaling")

    table_counts = [10, 50, 100, 250, 500]
    results = []

    original_schema = dict(sqlb.ALLOWED_SCHEMA)
    original_relations = dict(sqlb.RELATIONSHIP_GRAPH)

    for num_tables in table_counts:
        schema, relationships = _generate_schema(num_tables)
        blueprints = _make_blueprints(schema, relationships, count=min(10, num_tables))

        sqlb.ALLOWED_SCHEMA = schema
        sqlb.RELATIONSHIP_GRAPH = relationships

        compile_times = []
        sql_lengths = []
        errors = 0

        for _ in range(warmup):
            for bp in blueprints:
                try:
                    sqlb.build_secure_query(bp, tenant_id="bench_tenant")
                except Exception:
                    pass

        for _ in range(iterations):
            bp = random.choice(blueprints)
            t0 = time.perf_counter()
            try:
                sql, params = sqlb.build_secure_query(bp, tenant_id="bench_tenant")
                t1 = time.perf_counter()
                compile_times.append((t1 - t0) * 1000)
                sql_lengths.append(len(sql))
            except Exception:
                errors += 1
                t1 = time.perf_counter()
                compile_times.append((t1 - t0) * 1000)

        pct = _percentiles(compile_times)
        avg_len = statistics.mean(sql_lengths) if sql_lengths else 0

        results.append({
            "tables": num_tables,
            "iterations": iterations,
            "errors": errors,
            **pct,
            "avg_sql_len": round(avg_len),
        })

        print(f"\n  {num_tables:>4d} tables  │  {iterations:,} iterations  │  {errors} errors")
        print(f"  {'compile':>20s}  avg: {_format_ms(pct['avg'])}  p50: {_format_ms(pct['p50'])}  p95: {_format_ms(pct['p95'])}  p99: {_format_ms(pct['p99'])}")
        print(f"  {'sql length':>20s}  avg: {avg_len:.0f} chars")

    sqlb.ALLOWED_SCHEMA = original_schema
    sqlb.RELATIONSHIP_GRAPH = original_relations

    _print_header("PHASE 1 SUMMARY")
    print(f"  {'Tables':>8s}  {'p50':>10s}  {'p95':>10s}  {'p99':>10s}  {'max':>10s}  {'SQL len':>8s}")
    for r in results:
        print(f"  {r['tables']:>8d}  {_format_ms(r['p50']):>10s}  {_format_ms(r['p95']):>10s}  {_format_ms(r['p99']):>10s}  {_format_ms(r['max']):>10s}  {r['avg_sql_len']:>6d}ch")

    return results


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2: DATABASE
# ══════════════════════════════════════════════════════════════════════════

def _seed_table(cursor, table: str, columns: List[str], rows: int, tenant_id: str):
    """Batch-insert rows into a table."""
    import psycopg2
    col_str = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})"

    batch = []
    for i in range(rows):
        row = []
        for col in columns:
            if col == "tenant_id":
                row.append(tenant_id)
            elif col == "id":
                continue
            elif col == "name" or col == "product_name":
                row.append(f"item_{i}")
            elif col == "email":
                row.append(f"user_{i}@bench.test")
            elif col == "country":
                row.append(random.choice(["USA", "Germany", "India", "UK", "Japan"]))
            elif col == "status":
                row.append(random.choice(["active", "churned"]))
            elif col == "order_status":
                row.append(random.choice(["completed", "pending", "refunded"]))
            elif col == "total_amount":
                row.append(round(random.uniform(10, 2000), 2))
            elif col == "price":
                row.append(round(random.uniform(5, 500), 2))
            elif col == "stock_count":
                row.append(random.randint(0, 500))
            elif col == "category":
                row.append(random.choice(["Software", "Hardware", "Books"]))
            elif col == "customer_id":
                row.append(random.randint(1, max(1, rows // 10)))
            else:
                row.append(0)
        batch.append(tuple(row))

        if len(batch) >= 5000:
            psycopg2.extras.execute_batch(cursor, sql, batch, page_size=5000)
            batch = []
    if batch:
        psycopg2.extras.execute_batch(cursor, sql, batch, page_size=5000)


def phase2_database(dataset: str = "medium"):
    """Benchmark query execution against real database."""
    if not os.getenv("DATABASE_URL"):
        _print_header("PHASE 2: DATABASE — SKIPPED (no DATABASE_URL)")
        print("  Set DATABASE_URL to enable database benchmarks.")
        return None

    from app.database.connection import get_db_cursor, execute_secure_query
    from app.compiler.sql_builder import build_secure_query
    from app.database.cache import get_cached_results, set_cached_results, get_redis_client
    import psycopg2.extras

    dataset_configs = {
        "small": {"customers": 1_000, "orders": 5_000, "products": 500},
        "medium": {"customers": 10_000, "orders": 100_000, "products": 5_000},
        "large": {"customers": 100_000, "orders": 1_000_000, "products": 10_000},
    }

    sizes = dataset_configs.get(dataset, dataset_configs["medium"])

    _print_header(f"PHASE 2: DATABASE — {dataset.upper()} DATASET")
    print(f"  Seeding: {sizes['customers']:,} customers, {sizes['orders']:,} orders, {sizes['products']:,} products")

    try:
        with get_db_cursor() as cursor:
            for table, count in sizes.items():
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                existing = cursor.fetchone()["count"]
                if existing < count:
                    print(f"  Inserting {count - existing:,} rows into {table}...")
                    if table == "customers":
                        _seed_table(cursor, table, ["name", "email", "country", "status", "tenant_id"], count, "bench_tenant")
                    elif table == "orders":
                        _seed_table(cursor, table, ["customer_id", "total_amount", "order_status", "tenant_id"], count, "bench_tenant")
                    elif table == "products":
                        _seed_table(cursor, table, ["product_name", "price", "stock_count", "category", "tenant_id"], count, "bench_tenant")
    except Exception as e:
        print(f"  Seed failed: {e}")
        return None

    queries = [
        ("simple_select", {
            "target_table": "customers",
            "projection_columns": ["name", "email", "country"],
            "filters": [{"column": "country", "operator": "equals", "value": "USA"}],
            "sorting": {"column": "name", "direction": "asc"},
            "pagination": {"limit": 20, "offset": 0},
        }),
        ("join_query", {
            "target_table": "orders",
            "projection_columns": ["orders.id", "customers.name", "orders.total_amount"],
            "filters": [{"column": "total_amount", "operator": "greater_than", "value": 100}],
            "sorting": {"column": "total_amount", "direction": "desc"},
            "pagination": {"limit": 10, "offset": 0},
        }),
        ("aggregation", {
            "target_table": "orders",
            "aggregation": {"type": "sum", "column": "total_amount"},
            "filters": [{"column": "order_status", "operator": "equals", "value": "completed"}],
        }),
        ("count_all", {
            "target_table": "customers",
            "aggregation": {"type": "count", "column": "*"},
            "filters": [],
        }),
        ("ilike_filter", {
            "target_table": "products",
            "projection_columns": ["product_name", "price", "category"],
            "filters": [{"column": "product_name", "operator": "contains", "value": "item_"}],
            "sorting": {"column": "price", "direction": "asc"},
            "pagination": {"limit": 20, "offset": 0},
        }),
        ("pagination_deep", {
            "target_table": "orders",
            "projection_columns": ["id", "total_amount", "order_status"],
            "filters": [],
            "sorting": {"column": "id", "direction": "asc"},
            "pagination": {"limit": 100, "offset": 10000},
        }),
    ]

    iterations = 200
    results = []

    for name, blueprint in queries:
        sql, params = build_secure_query(blueprint, tenant_id="bench_tenant")

        compile_times = []
        exec_times = []
        row_counts = []

        for _ in range(iterations):
            t0 = time.perf_counter()
            sql, params = build_secure_query(blueprint, tenant_id="bench_tenant")
            t1 = time.perf_counter()
            compile_times.append((t1 - t0) * 1000)

            results_db, db_ms = execute_secure_query(sql, params, timeout_seconds=30)
            t2 = time.perf_counter()
            exec_times.append(db_ms)
            row_counts.append(len(results_db))

        compile_pct = _percentiles(compile_times)
        exec_pct = _percentiles(exec_times)
        avg_rows = statistics.mean(row_counts)

        results.append({"name": name, "compile": compile_pct, "exec": exec_pct, "avg_rows": round(avg_rows)})

        print(f"\n  {name}")
        print(f"    {'compile':>12s}  avg: {_format_ms(compile_pct['avg'])}  p50: {_format_ms(compile_pct['p50'])}  p95: {_format_ms(compile_pct['p95'])}  p99: {_format_ms(compile_pct['p99'])}")
        print(f"    {'db exec':>12s}  avg: {_format_ms(exec_pct['avg'])}  p50: {_format_ms(exec_pct['p50'])}  p95: {_format_ms(exec_pct['p95'])}  p99: {_format_ms(exec_pct['p99'])}")
        print(f"    {'rows':>12s}  avg: {avg_rows:.0f}")

    _print_header("PHASE 2 SUMMARY")
    print(f"  {'Query':<20s}  {'Compile p50':>12s}  {'Exec p50':>12s}  {'Exec p99':>12s}  {'Rows':>8s}")
    for r in results:
        print(f"  {r['name']:<20s}  {_format_ms(r['compile']['p50']):>12s}  {_format_ms(r['exec']['p50']):>12s}  {_format_ms(r['exec']['p99']):>12s}  {r['avg_rows']:>8.0f}")

    return results


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3: LOAD
# ══════════════════════════════════════════════════════════════════════════

def phase3_load(concurrency_levels: List[int] = None, duration: int = 10):
    """Concurrent pipeline load test (compile → cache → execute), bypassing LLM."""
    if concurrency_levels is None:
        concurrency_levels = [1, 10, 50, 100]

    _print_header("PHASE 3: LOAD — Pipeline Components (no LLM)")

    from app.compiler.sql_builder import build_secure_query
    from app.database.cache import get_cached_results, set_cached_results
    from app.database.connection import execute_secure_query

    blueprints = [
        {
            "target_table": "customers",
            "projection_columns": ["name", "email", "country"],
            "filters": [{"column": "country", "operator": "equals", "value": "USA"}],
            "sorting": {"column": "name", "direction": "asc"},
            "pagination": {"limit": 20, "offset": 0},
        },
        {
            "target_table": "orders",
            "projection_columns": ["id", "total_amount", "order_status"],
            "filters": [{"column": "total_amount", "operator": "greater_than", "value": 100}],
            "sorting": {"column": "total_amount", "direction": "desc"},
            "pagination": {"limit": 10, "offset": 0},
        },
        {
            "target_table": "products",
            "projection_columns": ["product_name", "price", "category"],
            "filters": [],
            "sorting": {"column": "price", "direction": "asc"},
            "pagination": {"limit": 20, "offset": 0},
        },
    ]

    results = []

    for users in concurrency_levels:
        compile_times = []
        cache_times = []
        execute_times = []
        total_times = []
        errors = 0
        successes = 0
        lock = threading.Lock()

        def make_request():
            nonlocal errors, successes
            bp = random.choice(blueprints)
            t_start = time.perf_counter()
            try:
                sql, params = build_secure_query(bp, tenant_id="bench_tenant")
                t_compile = time.perf_counter()

                cached = get_cached_results(sql, params)
                t_cache = time.perf_counter()

                if cached is None:
                    results_db, db_ms = execute_secure_query(sql, params, timeout_seconds=30)
                else:
                    results_db = cached
                    db_ms = 0
                t_exec = time.perf_counter()

                with lock:
                    compile_times.append((t_compile - t_start) * 1000)
                    cache_times.append((t_cache - t_compile) * 1000)
                    execute_times.append((t_exec - t_cache) * 1000)
                    total_times.append((t_exec - t_start) * 1000)
                    successes += 1
            except Exception:
                t_exec = time.perf_counter()
                with lock:
                    total_times.append((t_exec - t_start) * 1000)
                    errors += 1

        wall_start = time.perf_counter()

        with concurrent.futures.ThreadPoolExecutor(max_workers=users) as pool:
            futures = []
            end_time = wall_start + duration
            while time.perf_counter() < end_time:
                futures.append(pool.submit(make_request()))
                if len(futures) % users == 0:
                    time.sleep(0.01)
            concurrent.futures.wait(futures)

        wall_time = time.perf_counter() - wall_start
        total = successes + errors
        throughput = total / wall_time if wall_time > 0 else 0

        total_pct = _percentiles(total_times) if total_times else {"min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "avg": 0}
        compile_pct = _percentiles(compile_times) if compile_times else {"min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "avg": 0}
        cache_pct = _percentiles(cache_times) if cache_times else {"min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "avg": 0}
        exec_pct = _percentiles(execute_times) if execute_times else {"min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "avg": 0}
        error_rate = (errors / total * 100) if total > 0 else 0

        results.append({
            "users": users,
            "count": total,
            "successes": successes,
            "errors": errors,
            "error_rate": round(error_rate, 1),
            "throughput": round(throughput, 1),
            "wall_time": round(wall_time, 2),
            "total": total_pct,
            "compile": compile_pct,
            "cache": cache_pct,
            "execute": exec_pct,
        })

        print(f"\n  {users:>4d} threads  │  {total:>6d} requests  │  {wall_time:.1f}s  │  {errors} errors ({error_rate:.1f}%)")
        print(f"  {'throughput':>20s}  {throughput:,.1f} req/s")
        print(f"  {'total':>20s}  avg: {_format_ms(total_pct['avg'])}  p50: {_format_ms(total_pct['p50'])}  p95: {_format_ms(total_pct['p95'])}  p99: {_format_ms(total_pct['p99'])}")
        print(f"  {'compile':>20s}  avg: {_format_ms(compile_pct['avg'])}  p50: {_format_ms(compile_pct['p50'])}  p95: {_format_ms(compile_pct['p95'])}")
        print(f"  {'cache':>20s}  avg: {_format_ms(cache_pct['avg'])}  p50: {_format_ms(cache_pct['p50'])}  p95: {_format_ms(cache_pct['p95'])}")
        print(f"  {'db execute':>20s}  avg: {_format_ms(exec_pct['avg'])}  p50: {_format_ms(exec_pct['p50'])}  p95: {_format_ms(exec_pct['p95'])}")

    _print_header("PHASE 3 SUMMARY")
    print(f"  {'Threads':>8s}  {'Reqs':>8s}  {'Req/s':>10s}  {'Total p50':>12s}  {'Total p99':>12s}  {'Errors':>8s}")
    for r in results:
        print(f"  {r['users']:>8d}  {r['count']:>8d}  {r['throughput']:>10.1f}  {_format_ms(r['total']['p50']):>12s}  {_format_ms(r['total']['p99']):>12s}  {r['error_rate']:>6.1f}%")

    return results


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4: FAILURE
# ══════════════════════════════════════════════════════════════════════════

def phase4_failure():
    """Graceful degradation under fault conditions."""
    _print_header("PHASE 4: FAILURE — Fault Injection")

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    results = []

    # Test 1: Empty prompt
    resp = client.post("/api/v1/query/compile", json={"prompt": ""})
    passed = resp.status_code == 400
    results.append({"test": "Empty prompt", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"\n  {'✓' if passed else '✗'} Empty prompt → {resp.status_code} (expected 400)")

    # Test 2: Missing prompt
    resp = client.post("/api/v1/query/compile", json={})
    passed = resp.status_code == 422
    results.append({"test": "Missing prompt", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Missing prompt → {resp.status_code} (expected 422)")

    # Test 3: Prompt exceeding max length
    resp = client.post("/api/v1/query/compile", json={"prompt": "x" * 5000})
    passed = resp.status_code == 422
    results.append({"test": "Overlength prompt", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Overlength prompt → {resp.status_code} (expected 422)")

    # Test 4: Auth enforcement
    import os
    os.environ["REQUIRE_AUTH"] = "true"
    resp = client.post("/api/v1/query/compile", json={"prompt": "Show all customers"})
    passed = resp.status_code == 401
    results.append({"test": "Auth enforcement", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Auth enforcement → {resp.status_code} (expected 401)")
    os.environ["REQUIRE_AUTH"] = "false"

    # Test 5: Invalid API key
    os.environ["REQUIRE_AUTH"] = "true"
    resp = client.post(
        "/api/v1/query/compile",
        json={"prompt": "Show all customers"},
        headers={"X-Predicate-API-Key": "pred_invalid_key"},
    )
    passed = resp.status_code == 403
    results.append({"test": "Invalid API key", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Invalid API key → {resp.status_code} (expected 403)")
    os.environ["REQUIRE_AUTH"] = "false"

    # Test 6: Health endpoint
    resp = client.get("/health")
    passed = resp.status_code == 200 and resp.json().get("status") == "healthy"
    results.append({"test": "Health endpoint", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Health endpoint → {resp.status_code}")

    # Test 7: Readiness endpoint
    resp = client.get("/ready")
    passed = resp.status_code == 200
    results.append({"test": "Readiness endpoint", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Readiness endpoint → {resp.status_code}")

    # Test 8: Metrics endpoint
    resp = client.get("/metrics")
    passed = resp.status_code == 200 and "predicate_" in resp.text
    results.append({"test": "Metrics endpoint", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Metrics endpoint → {resp.status_code} (has Prometheus output: {passed})")

    # Test 9: Request ID in response
    resp = client.post(
        "/api/v1/query/compile",
        json={"prompt": "Show active customers in Germany"},
        headers={"X-Predicate-API-Key": "pred_live_7f8a9b2c3d4e5f6g7h8i9j0k"},
    )
    has_req_id = "x-request-id" in resp.headers
    results.append({"test": "Request ID header", "status": "PASS" if has_req_id else "FAIL"})
    print(f"  {'✓' if has_req_id else '✗'} X-Request-ID in response: {resp.headers.get('x-request-id', 'MISSING')}")

    # Test 10: Secure headers present
    has_xfo = "x-frame-options" in resp.headers
    has_xcto = "x-content-type-options" in resp.headers
    has_hsts = "strict-transport-security" in resp.headers
    all_headers = has_xfo and has_xcto and has_hsts
    results.append({"test": "Security headers", "status": "PASS" if all_headers else "FAIL"})
    print(f"  {'✓' if all_headers else '✗'} Security headers (X-Frame-Options, X-Content-Type-Options, HSTS): {'all present' if all_headers else 'MISSING'}")

    # Test 11: Export with empty prompt
    resp = client.post("/api/v1/export/async", json={"prompt": "   "})
    passed = resp.status_code == 400
    results.append({"test": "Export empty prompt", "status": "PASS" if passed else "FAIL", "code": resp.status_code})
    print(f"  {'✓' if passed else '✗'} Export empty prompt → {resp.status_code} (expected 400)")

    # Test 12: Trace in response
    resp = client.post(
        "/api/v1/query/compile",
        json={"prompt": "Show active customers in Germany"},
        headers={"X-Predicate-API-Key": "pred_live_7f8a9b2c3d4e5f6g7h8i9j0k"},
    )
    if resp.status_code == 200:
        data = resp.json()
        has_trace = "trace" in data and "spans" in data.get("trace", {})
        has_request_id = "request_id" in data
        results.append({"test": "Trace in response", "status": "PASS" if has_trace else "FAIL"})
        print(f"  {'✓' if has_trace else '✗'} Trace spans in response: {len(data.get('trace', {}).get('spans', []))} spans")
        results.append({"test": "Request ID in body", "status": "PASS" if has_request_id else "FAIL"})
        print(f"  {'✓' if has_request_id else '✗'} Request ID in response body: {data.get('request_id', 'MISSING')[:12]}...")
    else:
        results.append({"test": "Trace in response", "status": "SKIP"})
        results.append({"test": "Request ID in body", "status": "SKIP"})
        print(f"  ⊘ Trace/body checks skipped (query returned {resp.status_code})")

    passed_count = sum(1 for r in results if r["status"] == "PASS")
    total_count = sum(1 for r in results if r["status"] != "SKIP")

    _print_header("PHASE 4 SUMMARY")
    print(f"  {passed_count}/{total_count} tests passed")
    for r in results:
        icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊗"}[r["status"]]
        print(f"  {icon} {r['test']}")

    return results


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Predicate Performance Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phases:
  1  Compiler scaling (schema complexity 10–500 tables)
  2  Database execution (requires DATABASE_URL)
  3  Concurrent load test
  4  Failure injection

Examples:
  python benchmark.py
  python benchmark.py --phase 1
  python benchmark.py --phase 3 --users 100 --duration 30
  python benchmark.py --phase 2 --dataset large
        """,
    )
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4], help="Run a specific phase (default: all)")
    parser.add_argument("--users", type=int, default=50, help="Max concurrent users for phase 3 (default: 50)")
    parser.add_argument("--duration", type=int, default=10, help="Load test duration in seconds (default: 10)")
    parser.add_argument("--dataset", choices=["small", "medium", "large"], default="medium", help="Dataset size for phase 2")
    parser.add_argument("--iterations", type=int, default=5000, help="Iterations for phase 1 (default: 5000)")
    args = parser.parse_args()

    print("Predicate Performance Benchmark")
    print(f"  Python {sys.version.split()[0]}")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")

    start = time.perf_counter()

    if args.phase is None or args.phase == 1:
        phase1_compiler(iterations=args.iterations)
    if args.phase is None or args.phase == 2:
        phase2_database(dataset=args.dataset)
    if args.phase is None or args.phase == 3:
        levels = [1, 10, min(args.users, 50), args.users]
        levels = sorted(set(l for l in levels if l > 0))
        phase3_load(concurrency_levels=levels, duration=args.duration)
    if args.phase is None or args.phase == 4:
        phase4_failure()

    elapsed = time.perf_counter() - start
    _print_header("COMPLETE")
    print(f"  Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
