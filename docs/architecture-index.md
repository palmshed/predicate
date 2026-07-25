# Predicate Architecture Index

A plain index of functional topics across the palmshed/predicate codebase, organized by code location.

## Core Middlewares (app/auth/)

- **API Key Validation:** Header validation against a hardcoded tenant registry mapping corporate client accounts.
- **Rate Limiting:** Atomic fixed-window counters tracking traffic limits per minute across multi-tiered pricing plans using Redis.

## Semantic Translation (app/agent/)

- **Intermediate Blueprinting:** Parsing unformatted human input phrases into structured, strongly-typed JSON filter blueprints.
- **Pydantic Validation:** Strict response enforcement preventing formatting errors or unapproved parameter structures.

## Execution Matrix (app/compiler/)

- **Data Parameterization:** Separating query structures from input strings to neutralize SQL injection vulnerabilities.
- **Relational Mapping:** Generating dynamic database links (INNER JOIN) when requests span multiple datasets.
- **Multi-Tenant Confinement:** Injecting mandatory tenant filters to prevent data leakage between different workspaces.
- **Aggregation Operations:** Translating metric requests into mathematical functions (COUNT, SUM, AVG) while ignoring sorting constraints.

## Storage & Optimization (app/database/)

- **Query Replay Caching:** Intercepting requests using SHA-256 query signatures to serve records in sub-2ms from Redis memory.
- **Performance Telemetry:** Tracking total requests, cache hit percentages, and per-table data access counts.
- **Compliance Audit Sinking:** Writing an unalterable history log of all prompts, parameters, and query shapes to PostgreSQL.
- **Connection Pooling:** Initializing and recycling thread-safe database connection channels for horizontal scaling.

## Task Processing (app/worker.py)

- **Asynchronous Jobs:** Shifting long-running calculations to background workers via Celery to maintain responsive API endpoints.
- **Data Streaming:** Generating streaming CSV file payloads for large-scale data downloads.

## Verification Matrix (tests/)

- **Automated Suites:** 37 unit, security, integration, and aggregation tests executed automatically on code push via a GitHub Actions pipeline.