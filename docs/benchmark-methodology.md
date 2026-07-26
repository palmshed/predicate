# Benchmark Methodology

This document describes the benchmark suite for Predicate, an open-core NL-to-SQL middleware. The suite is implemented in `benchmark.py` at the project root and measures compiler performance, database throughput, concurrent load handling, and failure resilience.

## Phases

The benchmark suite executes four distinct phases, each targeting a different component of the system.

### Phase 1: Compiler Benchmarks

Phase 1 evaluates the SQL compiler's performance under increasing schema complexity. It dynamically generates `ALLOWED_SCHEMA` and `RELATIONSHIP_GRAPH` definitions for schema sizes of 10, 50, 100, 250, and 500 tables. For each schema size, valid blueprints are generated and `build_secure_query()` is invoked repeatedly to measure compilation latency.

- **Iterations:** 5000 per schema size
- **Warmup:** 500 iterations (discarded from results)
- **Metrics reported:** p50, p95, p99, max latency, average SQL length

### Phase 2: Database Benchmarks

Phase 2 measures end-to-end query execution against real database instances. It requires the `DATABASE_URL` environment variable to be set. If the target database contains insufficient data, the suite seeds required tables (customers, orders, products) automatically.

**Dataset sizes:**

| Dataset | Customers | Orders | Products |
|---------|-----------|--------|----------|
| small   | 1,000     | 5,000  | 500      |
| medium  | 10,000    | 100,000| 5,000    |
| large   | 100,000   | 1,000,000 | 10,000 |

**Query patterns tested (6 total):**
1. `simple_select`
2. `join_query`
3. `aggregation`
4. `count_all`
5. `ilike_filter`
6. `pagination_deep`

- **Iterations:** 200 per query pattern
- **Metrics reported:** compile latency, database execution latency, row counts

### Phase 3: Load Test

Phase 3 exercises the pipeline components directly without invoking an LLM. It chains `build_secure_query`, `get_cached_results`, and `execute_secure_query` under concurrent load using a thread pool.

- **Concurrency levels:** 1, 10, 50, 100 threads (configurable)
- **Duration:** 10 seconds per concurrency level (configurable)
- **Metrics reported:** throughput (requests/second), total latency percentiles, compile latency percentiles, cache latency percentiles, execute latency percentiles, error rate

### Phase 4: Failure Injection

Phase 4 validates graceful degradation under fault conditions. It consists of 13 tests covering the following categories:

- **Input validation:** empty prompt, missing prompt, overlength prompt
- **Authentication:** enforcement of required credentials, behavior with invalid keys
- **Endpoints:** health check, readiness probe, metrics endpoint
- **Request correlation:** validation of `X-Request-ID` header presence and propagation in response body
- **Security headers:** presence of `X-Frame-Options`, `X-Content-Type-Options`, and HSTS headers
- **Export validation:** empty prompt handling in export flow
- **Trace spans:** verification that trace spans are included in responses

All tests use `TestClient` and require no external services.

## Usage

Run all phases:

```
python benchmark.py
```

Run a specific phase:

```
python benchmark.py --phase 1
```

Configure concurrency and duration for the load test:

```
python benchmark.py --phase 3 --users 100 --duration 30
```

Select a dataset size for database benchmarks:

```
python benchmark.py --phase 2 --dataset large
```

## Environment Requirements

| Phase | DATABASE_URL | Redis | External Dependencies |
|-------|-------------|-------|----------------------|
| 1     | No          | No    | None (pure Python)   |
| 2     | Yes         | Yes   | PostgreSQL or compatible |
| 3     | No          | Yes   | None                 |
| 4     | No          | No    | None (TestClient)    |

## Reproducibility

- Timing is captured with `time.perf_counter()` for high-resolution measurement across platforms.
- Thread-safe metric collection uses `threading.Lock` to prevent data corruption under concurrent load.
- Blueprints are selected randomly during each iteration to produce a realistic workload distribution.
- The suite has no external dependencies beyond those already required by the Predicate project.
