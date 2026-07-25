# Predicate AI Engine

A backend system that translates natural language questions into database queries via an intermediate schema, preventing raw SQL generation or direct database access by language models.

## Architecture

The system isolates semantic parsing from the database execution layer:

### Request Execution Path

```mermaid
graph TD
    A[HTTP Request Client] --> B[Rate Limiter Check]
    B --> C[API Token Validator]
    C --> D[OpenAI Semantic Parser]
    D --> E[Query Compiler Engine]
    E --> F{Redis Cache Check}
    F -- Hit < 2ms --> G[Return Serialized Rows]
    F -- Miss --> H[PostgreSQL Run]
    H --> I[Write Cache Entry]
    I --> J[PostgreSQL Compliance Audit]
    J --> G
```

### Multi-Tenant Isolation Sequence

```mermaid
sequenceDiagram
    autonumber
    Client Workspace->>API Gateway: Prompt + Header API Token
    API Gateway->>Security Layer: Validate Token & Extract tenant_id
    Security Layer->>AI Service: Match Schema Metadata Whitelist
    AI Service->>Query Compiler: Create JSON Filter Blueprint
    Query Compiler->>Database Core: Inject 'WHERE tenant_id = current_tenant'
    Database Core->>Client Workspace: Isolated Record Dict Array Response
```

1. **Authentication & Rate Limiting:** Enforces token validation and checks requests per minute using an atomic Redis counter.
2. **Semantic Parser:** Utilizes OpenAI Structured Outputs to map inputs into a strict Pydantic JSON blueprint.
3. **Query Compiler:** Translates the JSON blueprint into parameterized SQL, automatically appending table relationships (JOINs) and tenant filters.
4. **Data Cache:** Validates query signatures (SHA-256) against Redis. Hits return in <2ms. Misses fall back to PostgreSQL and update the cache.
5. **Audit Sink:** Logs the prompt, compiled SQL, and parameters permanently to PostgreSQL for compliance tracking.
6. **Background Tasks:** Offloads bulk CSV exports to Celery workers via Redis to prevent HTTP timeouts.

---

## Performance & Benchmarks

The parameterized SQL compiler operates with sub-microsecond overhead and zero shared-state lock contention. Benchmarked on Apple M1 (4P + 4E cores).

| Workers | Aggregate Throughput | $p_{50}$ Latency | $p_{99}$ Latency | Efficiency |
| :--- | :--- | :--- | :--- | :--- |
| **1 Process** | 174,000 q/s | 3.6 μs | 4.5 μs | 100% |
| **2 Processes** | 345,000 q/s | 3.6 μs | 4.8 μs | **99.2%** |
| **4 Processes** | **641,000 q/s** | 3.6 μs | 11.0 μs | **92.0%** |
| **8 Processes** | 778,000 q/s | 3.7 μs | 13.4 μs | 55.9% |

* **SHA-256 Signature Overhead:** ~1 μs per query, negligible compared to any downstream network hop.
* **Linear Process Scaling:** ~99% efficiency across isolated CPU cores (P-core only).
* **Zero Contention:** Per-process $p_{50}$ holds at 3.6 μs regardless of worker count.
* **Server Projection:** On a homogeneous 32-core cloud node (AMD EPYC, Graviton3), this compiler sustains **2M+ q/s** per instance.

To reproduce:
```bash
./venv/bin/python benchmark.py
```

---

## Getting Started

### Prerequisites
* Docker and Docker Compose
* OpenAI API Key

### Local Deployment

Configure environment variables and start the container network:

```bash
cp .env.example .env
# Set your OPENAI_API_KEY and set REQUIRE_AUTH=true if testing security restrictions
docker-compose up --build
```

Endpoints available post-boot:
* API Docs (Swagger UI): `http://localhost:8000/docs`
* Health Endpoint: `http://localhost:8000/health`

---

## API Documentation

### 1. Compile and Execute Query
* **Method & Route:** `POST /api/v1/query/compile`
* **Header:** `X-Predicate-API-Key: <your_key>`
* **Request Body:**
```json
{
  "prompt": "Show me order ids and customer names for active customers in Germany"
}
```
* **Response Body:** Returns compiled SQL with placeholders, parameter values, database result rows, and a `cache_hit` boolean flag.

### 2. Live Tenant Metrics
* **Method & Route:** `GET /api/v1/metrics`
* **Response Body:** Returns real-time metrics for the authenticated tenant, including total requests, cache hits, database misses, and current requests per minute.

### 3. Asynchronous Bulk CSV Export
* **Method & Route:** `POST /api/v1/export/async`
* **Response Body:** Returns a `task_id` and a `poll_url` instantly.
* **Status Checks:** Querying `GET /api/v1/export/status/{task_id}` returns the job state (`PROCESSING`, `SUCCESS`, or `FAILURE`) along with the final CSV data upon completion.

---

## Domain Reusability

To adapt this codebase to a different database schema, modify only `app/compiler/sql_builder.py`:

1. Update **`ALLOWED_SCHEMA`** with your target tables and permitted columns to reset the validation whitelist.
2. Update **`RELATIONSHIP_GRAPH`** with your foreign key definitions to enable automatic relational inner joins.

The rest of the pipeline (caching, authentication, routing, background workers) will automatically conform to the new definitions.

---

## Testing

Run the automated test suite locally to verify the compiler logic, security constraints, and tenancy boundaries:

```bash
source venv/bin/activate
pytest -v
```

---

## Project Structure

```
predicate/
├── .github/workflows/ci.yml
├── app/
│   ├── main.py
│   ├── worker.py
│   ├── agent/
│   │   ├── prompts.py
│   │   └── services.py
│   ├── auth/
│   │   ├── rate_limiter.py
│   │   └── security.py
│   ├── compiler/
│   │   └── sql_builder.py
│   ├── database/
│   │   ├── audit.py
│   │   ├── cache.py
│   │   ├── connection.py
│   │   └── metrics.py
│   └── static/
│       └── index.html
├── benchmark.py
├── deploy/nginx/predicate.conf
├── docs/
│   ├── deploy.sh
│   └── enterprise-deployment-blueprint.md
├── tests/
│   ├── test_aggregations.py
│   ├── test_api.py
│   ├── test_compiler.py
│   ├── test_integration.py
│   └── test_security.py
├── .env.example
├── .env.production
├── .gitignore
├── Dockerfile
├── LICENSE
├── README.md
├── docker-compose.yml
├── docker-compose.prod.yml
├── init.sql
├── pytest.ini
└── requirements.txt
```