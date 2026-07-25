import time
import os
import statistics
import concurrent.futures
from app.compiler.sql_builder import build_secure_query
from app.database.cache import generate_cache_key

BLUEPRINTS = [
    {
        "name": "simple_filter",
        "blueprint": {
            "target_table": "customers",
            "projection_columns": ["id", "name", "email"],
            "filters": [{"column": "country", "operator": "equals", "value": "Germany"}],
            "sorting": {"column": "name", "direction": "asc"},
            "pagination": {"limit": 20, "offset": 0}
        }
    },
    {
        "name": "join_multi_filter",
        "blueprint": {
            "target_table": "orders",
            "projection_columns": ["orders.id", "customers.name", "orders.total_amount"],
            "filters": [
                {"column": "total_amount", "operator": "greater_than", "value": 500},
                {"column": "customers.status", "operator": "equals", "value": "active"}
            ],
            "sorting": {"column": "total_amount", "direction": "desc"},
            "pagination": {"limit": 10, "offset": 0}
        }
    },
    {
        "name": "ilike_search",
        "blueprint": {
            "target_table": "products",
            "projection_columns": ["product_name", "price", "category"],
            "filters": [{"column": "product_name", "operator": "contains", "value": "wireless"}],
            "sorting": {"column": "price", "direction": "asc"},
            "pagination": {"limit": 20, "offset": 0}
        }
    },
    {
        "name": "sum_aggregation",
        "blueprint": {
            "target_table": "orders",
            "aggregation": {"type": "sum", "column": "total_amount"},
            "filters": [{"column": "order_status", "operator": "equals", "value": "completed"}]
        }
    },
    {
        "name": "count_aggregation",
        "blueprint": {
            "target_table": "customers",
            "aggregation": {"type": "count", "column": "*"},
            "filters": []
        }
    },
    {
        "name": "join_with_sorting",
        "blueprint": {
            "target_table": "orders",
            "projection_columns": ["orders.id", "orders.total_amount", "orders.purchase_date"],
            "filters": [{"column": "customers.country", "operator": "equals", "value": "India"}],
            "sorting": {"column": "orders.purchase_date", "direction": "desc"},
            "pagination": {"limit": 5, "offset": 0}
        }
    }
]

ITERATIONS = 10000
WARMUP = 1000
TENANT_ID = "tenant_alpha"
WORKER_COUNTS = [1, 2, 4, 8]
PROC_QUERIES = 200000
PROC_WARMUP = 5000
CORES = os.cpu_count() or 4


def compute_percentiles(data):
    s = sorted(data)
    n = len(s)
    return {
        "avg": statistics.mean(s),
        "p50": s[n // 2],
        "p95": s[int(n * 0.95)],
        "p99": s[int(n * 0.99)],
        "min": s[0],
        "max": s[-1],
    }


def run_single_threaded():
    print("=" * 70)
    print("PHASE 1: SINGLE-THREADED (with warmup)")
    print(f"  Warmup: {WARMUP:,} | Measured: {ITERATIONS:,} per blueprint")
    print("=" * 70)

    all_compile = []
    all_hash = []

    for test in BLUEPRINTS:
        for _ in range(WARMUP):
            sql, params = build_secure_query(test["blueprint"], tenant_id=TENANT_ID)
            generate_cache_key(sql, params)

        compile_times = []
        hash_times = []
        for _ in range(ITERATIONS):
            t0 = time.perf_counter_ns()
            sql, params = build_secure_query(test["blueprint"], tenant_id=TENANT_ID)
            t1 = time.perf_counter_ns()
            generate_cache_key(sql, params)
            t2 = time.perf_counter_ns()

            compile_times.append(t1 - t0)
            hash_times.append(t2 - t1)

        all_compile.extend(compile_times)
        all_hash.extend(hash_times)

        c = compute_percentiles(compile_times)
        h = compute_percentiles(hash_times)
        print(f"\n{'─' * 70}")
        print(f"  {test['name']}")
        print(f"{'─' * 70}")
        print(f"  Compile  — avg: {c['avg']/1000:8.2f}us | p50: {c['p50']/1000:8.2f}us | p95: {c['p95']/1000:8.2f}us | p99: {c['p99']/1000:8.2f}us")
        print(f"  SHA-256  — avg: {h['avg']/1000:8.2f}us | p50: {h['p50']/1000:8.2f}us | p95: {h['p95']/1000:8.2f}us | p99: {h['p99']/1000:8.2f}us")

    c = compute_percentiles(all_compile)
    h = compute_percentiles(all_hash)
    total_ns = sum(all_compile) + sum(all_hash)
    total = len(all_compile)
    total_s = total_ns / 1_000_000_000

    print(f"\n{'=' * 70}")
    print("SINGLE-THREADED AGGREGATE")
    print(f"{'=' * 70}")
    print(f"  Queries: {total:,} | Time: {total_s:.4f}s | Throughput: {total/total_s:,.0f} q/s")
    print(f"\n  Compile  — avg: {c['avg']/1000:8.2f}us | p50: {c['p50']/1000:8.2f}us | p95: {c['p95']/1000:8.2f}us | p99: {c['p99']/1000:8.2f}us | min: {c['min']/1000:8.2f}us | max: {c['max']/1000:8.2f}us")
    print(f"  SHA-256  — avg: {h['avg']/1000:8.2f}us | p50: {h['p50']/1000:8.2f}us | p95: {h['p95']/1000:8.2f}us | p99: {h['p99']/1000:8.2f}us")

    compile_pct = sum(all_compile) / total_ns * 100
    hash_pct = sum(all_hash) / total_ns * 100
    print(f"\n  Time distribution: Compile {compile_pct:.1f}% | SHA-256 {hash_pct:.1f}%")
    print(f"{'=' * 70}")

    return total / total_s


def _worker_task(blueprint, tenant_id, count):
    compile_times = []
    hash_times = []
    for _ in range(count):
        t0 = time.perf_counter_ns()
        sql, params = build_secure_query(blueprint, tenant_id=tenant_id)
        t1 = time.perf_counter_ns()
        generate_cache_key(sql, params)
        t2 = time.perf_counter_ns()
        compile_times.append(t1 - t0)
        hash_times.append(t2 - t1)
    return compile_times, hash_times


def run_concurrent():
    print(f"\n{'=' * 70}")
    print("PHASE 2: CONCURRENCY (lock contention test)")
    print(f"  Workers: {WORKER_COUNTS} | Queries per worker: {ITERATIONS:,}")
    print(f"{'=' * 70}")

    concurrency_results = []

    for worker_count in WORKER_COUNTS:
        queries_per_worker = ITERATIONS // worker_count
        blueprint = BLUEPRINTS[0]

        for _ in range(WARMUP):
            build_secure_query(blueprint["blueprint"], tenant_id=TENANT_ID)

        wall_start = time.perf_counter_ns()

        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(_worker_task, blueprint["blueprint"], TENANT_ID, queries_per_worker)
                for _ in range(worker_count)
            ]
            results = [f.result() for f in futures]

        wall_ns = time.perf_counter_ns() - wall_start

        all_compile = []
        all_hash = []
        for ct, ht in results:
            all_compile.extend(ct)
            all_hash.extend(ht)

        total = len(all_compile)
        wall_s = wall_ns / 1_000_000_000
        throughput = total / wall_s

        c = compute_percentiles(all_compile)
        h = compute_percentiles(all_hash)

        print(f"\n{'─' * 70}")
        print(f"  {worker_count} worker{'s' if worker_count > 1 else ''} | {total:,} queries | {wall_s:.4f}s wall time")
        print(f"{'─' * 70}")
        print(f"  Throughput:        {throughput:,.0f} q/s")
        print(f"  Compile avg:       {c['avg']/1000:8.2f}us | p99: {c['p99']/1000:8.2f}us | max: {c['max']/1000:8.2f}us")
        print(f"  SHA-256 avg:       {h['avg']/1000:8.2f}us | p99: {h['p99']/1000:8.2f}us")

        concurrency_results.append((worker_count, throughput))

    print(f"\n{'=' * 70}")
    print("CONCURRENCY SCALING")
    print(f"{'=' * 70}")
    base = concurrency_results[0][1]
    for workers, tput in concurrency_results:
        efficiency = (tput / base) / workers * 100
        print(f"  {workers:2d} workers → {tput:>12,.0f} q/s | {tput/base:6.2f}x speedup | {efficiency:5.1f}% efficiency")
    print(f"{'=' * 70}")

    return concurrency_results


def _process_init(blueprint_dict, tenant_id, warmup_count, count):
    for _ in range(warmup_count):
        build_secure_query(blueprint_dict, tenant_id=tenant_id)
    compile_times = []
    hash_times = []
    for _ in range(count):
        t0 = time.perf_counter_ns()
        sql, params = build_secure_query(blueprint_dict, tenant_id=tenant_id)
        t1 = time.perf_counter_ns()
        generate_cache_key(sql, params)
        t2 = time.perf_counter_ns()
        compile_times.append(t1 - t0)
        hash_times.append(t2 - t1)
    return compile_times, hash_times


def run_multiprocess():
    print(f"\n{'=' * 70}")
    print("PHASE 3: MULTI-PROCESS (GIL bypass — true CPU scaling)")
    print(f"  CPU cores: {CORES} | Queries per process: {PROC_QUERIES:,} | Warmup: {PROC_WARMUP:,}")
    proc_counts = [c for c in [1, 2, 4, min(8, CORES)] if c <= CORES]
    if CORES not in proc_counts:
        proc_counts.append(CORES)
    proc_counts = sorted(set(proc_counts))
    print(f"  Process counts: {proc_counts}")
    print(f"{'=' * 70}")

    blueprint = BLUEPRINTS[0]["blueprint"]
    process_results = []

    for proc_count in proc_counts:
        total_queries = PROC_QUERIES * proc_count

        wall_start = time.perf_counter_ns()

        with concurrent.futures.ProcessPoolExecutor(max_workers=proc_count) as executor:
            futures = [
                executor.submit(_process_init, blueprint, TENANT_ID, PROC_WARMUP, PROC_QUERIES)
                for _ in range(proc_count)
            ]
            results = [f.result() for f in futures]

        wall_ns = time.perf_counter_ns() - wall_start

        all_compile = []
        all_hash = []
        per_proc_stats = []
        for ct, ht in results:
            all_compile.extend(ct)
            all_hash.extend(ht)
            cc = compute_percentiles(ct)
            ch = compute_percentiles(ht)
            per_proc_stats.append((cc, ch))

        wall_s = wall_ns / 1_000_000_000
        aggregate_throughput = total_queries / wall_s

        print(f"\n{'─' * 70}")
        print(f"  {proc_count} process{'es' if proc_count > 1 else ''} | {total_queries:,} queries | {wall_s:.4f}s wall time")
        print(f"{'─' * 70}")
        print(f"  Aggregate throughput: {aggregate_throughput:>12,.0f} q/s")

        print(f"\n  Per-process breakdown:")
        for i, (cc, ch) in enumerate(per_proc_stats):
            print(f"    Process {i}: compile p50={cc['p50']/1000:7.2f}us p99={cc['p99']/1000:7.2f}us | SHA-256 avg={ch['avg']/1000:5.2f}us")

        c = compute_percentiles(all_compile)
        h = compute_percentiles(all_hash)
        print(f"\n  Aggregate: compile avg={c['avg']/1000:.2f}us p50={c['p50']/1000:.2f}us p99={c['p99']/1000:.2f}us max={c['max']/1000:.2f}us")
        print(f"             SHA-256 avg={h['avg']/1000:.2f}us p99={h['p99']/1000:.2f}us")

        process_results.append((proc_count, aggregate_throughput))

    print(f"\n{'=' * 70}")
    print("MULTI-PROCESS SCALING")
    print(f"{'=' * 70}")
    base = process_results[0][1]
    for procs, tput in process_results:
        speedup = tput / base
        efficiency = speedup / procs * 100
        print(f"  {procs:2d} process{'es' if procs > 1 else ' '} → {tput:>12,.0f} q/s | {speedup:6.2f}x speedup | {efficiency:5.1f}% efficiency")
    print(f"{'=' * 70}")

    return process_results


if __name__ == "__main__":
    serial_tput = run_single_threaded()
    concurrency_results = run_concurrent()
    process_results = run_multiprocess()
