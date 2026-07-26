# Predicate v1.0.0 -- Release Notes

**Date:** 2026-07-26

## What is Predicate?

Predicate is an open-core natural language to SQL compilation middleware. It translates plain-English questions into parameterized SQL queries through a structured JSON blueprint, preventing language models from ever touching raw SQL.

## What this release delivers

### For developers

A complete workspace for writing and testing natural language queries against your database. The IDE-style UI includes a command palette, keyboard shortcuts, query history, schema explorer, and a results table with sort, filter, and export.

### For security engineers

A compiler-based architecture that isolates the LLM from SQL generation. The LLM produces a validated JSON blueprint. The compiler generates parameterized SQL from a schema whitelist. Combined with tenant isolation, read-only database roles, CSRF protection, secure headers, input validation, and query timeouts, these layers provide defense in depth.

### For platform teams

Structured JSON logging with request ID correlation, trace spans across the compile-validate-execute pipeline, Prometheus metrics, and health/readiness endpoints. A four-phase benchmark suite validates compiler performance, database throughput, concurrent load handling, and failure resilience.

## Key numbers

- **37/37 tests passing**
- **13/13 failure injection tests passing**
- **Sub-microsecond compiler latency** (10-500 tables)
- **802 req/s** pipeline throughput at 10 concurrent threads
- **641,000 q/s** compiler throughput at 4 processes

## Getting started

```bash
git clone https://github.com/palmshed/predicate.git
cd predicate
cp .env.example .env
# Set your LLM API key (OpenRouter free tier works)
docker-compose up --build
```

Open http://localhost:8000 and type a question about your data.

## Documentation

- [README](README.md) -- architecture, API, configuration
- [Threat Model](docs/threat-model.md) -- security assumptions and analysis
- [Deployment Guide](docs/deployment.md) -- local, Docker, production
- [Operations Guide](docs/operations.md) -- monitoring, failure modes, backup
- [Benchmark Methodology](docs/benchmark-methodology.md) -- how to reproduce results
- [CHANGELOG](CHANGELOG.md) -- complete list of changes

## License

MIT
