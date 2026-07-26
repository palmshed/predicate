# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-26

### Added

**Frontend**
- Complete UI rewrite (React, IDE-style workspace)
- Command palette (Ctrl+K / Cmd+K)
- Query history with localStorage persistence
- Schema explorer with keyboard-navigable tree
- Virtual results table (sort, filter, column resize, inline edit)
- Three themes: Light, Dim, Dark
- Keyboard shortcuts: C (copy SQL), E (export CSV), T (cycle theme), ? (help)

**Security**
- Secure headers middleware (X-Frame-Options DENY, X-Content-Type-Options nosniff, HSTS, CSP, Referrer-Policy, Permissions-Policy)
- CSRF protection (signed cookie + header match, browser-only enforcement)
- Input validation (MAX_PROMPT_LENGTH=2000, Pydantic models)
- Query timeouts (QUERY_TIMEOUT_SECONDS=30)
- Read-only database role (predicate_reader with SELECT-only grants)
- CORS configuration via ALLOWED_ORIGINS

**Observability**
- Structured JSON logging with contextvars (request_id, tenant_id)
- X-Request-ID correlation via middleware
- TraceContext with named spans (compile, validate, cache_lookup, execute)
- Prometheus metrics (/metrics endpoint)
- Per-provider metrics (compile duration by provider)
- Health endpoint (/health) with version, git commit, build date, uptime, memory, PID
- Readiness endpoint (/ready)

**Database**
- Extended audit_logs table (request_id, compile_ms, validate_ms, execute_ms, rows_returned, target_table, error_code)
- Read-only connection pool (DATABASE_READONLY_URL)
- Execute query returns (results, db_query_ms) tuple for timing separation

**Benchmarking**
- Four-phase benchmark suite (compiler scaling, database execution, concurrent load, failure injection)
- CLI with argparse (phase selection, concurrency, duration, dataset size)
- Compiler benchmarks across schema complexity (10–500 tables)
- Pipeline load test bypassing LLM (802 req/s at 10 threads)
- 13 failure injection tests (all passing)

**Infrastructure**
- GitHub Actions CI (Python 3.14, 37 tests, live Postgres+Redis)
- GitHub Pages deployment for website
- Nginx production config (TLS 1.2/1.3, HSTS, security headers)
- Docker Compose production configuration
- Alembic migration setup

**Documentation**
- Threat model (docs/threat-model.md) with security assumptions
- Benchmark methodology (docs/benchmark-methodology.md)
- Production readiness checklist (docs/production-readiness.md)
- Deployment guide (docs/deployment.md)
- Operations guide (docs/operations.md)

### Changed

- LLM provider is now configurable via LLM_PROVIDER env var (openai or openrouter)
- Default LLM provider changed to openrouter (free tier, no credit card required)
- Current model: nvidia/nemotron-3-super-120b-a12b:free
- Health endpoint now reports llm_provider, llm_key_configured, version, git_commit, build_date, uptime, memory, PID
- Hero image is now code-generated SVG (hero/build.js) instead of static PNG

### Fixed

- Audit sink failures no longer crash request handling (graceful degradation)
- Rate limiter bypasses gracefully when Redis is unavailable
