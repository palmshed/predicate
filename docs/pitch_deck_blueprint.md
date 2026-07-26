# Predicate: Investor Pitch Deck Blueprint

## Slide 1: The Hook

**Headline:** Predicate: The Secure Natural Language Layer for Enterprise Data.

**Visual Anchor:** A high-contrast graphic showing text transforming cleanly into structured code blocks.

**Core Message:** Allowing non-technical teams to query databases instantly using plain text, without risking security or hallucinations.

---

## Slide 2: The Core Problem

**Headline:** Data is Trapped Behind Engineering Bottlenecks or Exposed to AI Hallucinations.

- **The Technical Moat:** Marketing, sales, and executive teams wait days for busy backend engineers to write custom SQL reports.
- **The Security Nightmare:** Passing raw natural language to an LLM and letting it write direct database code creates severe data leakage risks, memory vulnerabilities, and accidental database deletions (DROP TABLE).

---

## Slide 3: The Solution

**Headline:** A Relational, Deterministic Gateway for Secure AI Business Intelligence.

- **No Direct DB Access:** AI agents remain entirely isolated from target cloud instances and connection pools.
- **Multi-Table Schema Graph:** The agent parses compound user questions into validated JSON schemas mapping independent data tables.
- **The Relational Compiler:** Predicate's custom backend engine programmatically injects safe, structural INNER JOIN strings and parameterized filters, neutralizing data leak vectors.

---

## Slide 4: Underlying Technology

**Headline:** Sub-2ms In-Memory Caching Married with Ironclad DB Whitelisting.

- **Dual-Tier Isolation:** Utilizing cryptographic SHA-256 query signatures to intercept recurring requests at the memory tier via Redis.
- **Zero-Compute Replays:** Duplicate dashboard updates and identical business lookups bypass PostgreSQL completely, dropping latency down to sub-2ms.
- **Enterprise Runtime Stack:** Synchronous FastAPI web routers, resilient thread-safe connection pooling, Redis caching nodes, and multi-container Docker infrastructure orchestration.

---

## Slide 5: Product Walkthrough

**Headline:** From Intent to Inspected Record Rows in Under 500ms.

1. **User Action:** A support manager types: "Show order IDs and total amounts for customers living in Germany."
2. **Agent Translation:** Semantic translation extracts parameters with cross-table dot notation:
   ```json
   {"target_table": "orders", "projection_columns": ["id", "total_amount"], "filters": [{"column": "customers.country", "operator": "equals", "value": "Germany"}]}
   ```
3. **Safe Execution:** The relational compiler generates:
   ```sql
   SELECT orders.id, orders.total_amount FROM orders INNER JOIN customers ON orders.customer_id = customers.id WHERE 1=1 AND customers.country = %s LIMIT 20;
   ```
4. **Cache Check:** Redis intercepts via SHA-256 query signature. Cache hit → sub-2ms response. Cache miss → PostgreSQL execution → result stored with 5-minute TTL.
5. **UI Return:** Clean, aggregated, human-readable data records returned with `cache_hit` flag.

---

## Slide 6: Market Opportunity

**Headline:** Empowering the 90% of Enterprise Workers Who Can't Code.

- **TAM:** The global cloud analytics and AI business intelligence market is scaling rapidly.
- **Target Segment:** Mid-market B2B SaaS corporations, financial institutions, and logistics networks managing large databases with non-technical operational workforces.

---

## Slide 7: Business Model

**Headline:** Predictable, Usage-Based B2B SaaS Tiers.

| Tier | Description |
|------|-------------|
| **Developer** | Free local Docker development cluster configuration sandbox for evaluation. |
| **Growth** | Fixed seat licensing for growing operational teams executing standard metrics pipelines. |
| **Enterprise** | Custom on-premise cloud infrastructure deployments mapping specialized, isolated schema dictionaries. |

---

## Slide 8: The Competitive Edge

**Headline:** The Predicate Paradigm vs. Alternatives.

| Alternative | Limitation | Predicate Advantage |
|-------------|------------|---------------------|
| **Visual Query Builders** | Force non-technical workers to master intricate visual relational map logic and data schema properties. | Natural language input with automatic JOIN resolution, no schema knowledge required. |
| **Naive AI Generation** | Let unstructured LLMs construct raw SQL, frequently breaking database connections, hallucinating fields, or spiking database CPU costs on repetitive analytical queries. | Restricts AI to metadata filters, enforces safe graph joins via code boundaries, and optimizes high-frequency execution using a secure distributed caching layer. |
| **Custom In-House** | Requires dedicated backend engineers to build and maintain query logic, whitelists, and security boundaries. | Open-core boilerplate framework, teams update one schema file and deploy immediately. |

---

## Slide 9: Go-To-Market Strategy

**Headline:** Scaling via Frictionless Local Sandbox Developer Adoption.

- **Open Core Seed:** Open-sourcing the standalone local Docker compilation engine to build organic engineer trust and developer community distribution.
- **Plug-and-Play Hub:** Providing pre-built connectors for major database ecosystems like AWS RDS and cloud warehouses.

---

## Slide 10: The Ask

**Headline:** Help Us Decouple Enterprise Data From Engineering Backlogs.

- **Milestone Focus:** Seeking pre-seed funding to expand database integration connectors and optimize native semantic translation routing.
- **Contact:** Founder details, repository link, and team credentials.

---

## Technical Architecture Reference

```
User Text Input
       |
       v
[ AI Agent Layer ]  -- Pydantic Structured Outputs + Dot Notation
       |
       v
[ JSON Blueprint ]  -- Validated, typed filter schema with cross-table references
       |
       v
[ SQL Compiler ]    -- Whitelist enforcement + RELATIONSHIP_GRAPH JOIN injection
       |
       v
[ Redis Cache ]     -- SHA-256 query signature lookup (sub-2ms)
       |  (miss)
       v
[ PostgreSQL ]      -- Connection pool, parameterized execution
       |
       v
[ Cache Write ]     -- Store results with TTL
       |
       v
[ Results ]         -- Dict rows + cache_hit flag returned to user
```

## Repository

```
predicate/
├── app/
│   ├── main.py              # FastAPI entry point + cache interception
│   ├── worker.py            # Celery background tasks
│   ├── agent/
│   │   ├── prompts.py       # AI system prompt
│   │   └── services.py      # Multi-provider LLM layer (OpenAI, OpenRouter)
│   ├── auth/
│   │   ├── security.py      # API key validation
│   │   └── rate_limiter.py  # Redis rate limiting
│   ├── compiler/
│   │   └── sql_builder.py   # JOIN-aware parameterized SQL generation
│   └── database/
│       ├── connection.py    # PostgreSQL connection pooling
│       ├── cache.py         # Redis caching tier
│       ├── metrics.py       # Tenant metrics
│       └── audit.py         # Compliance audit log
├── alembic/                 # Database migrations
├── tests/                   # pytest suite (37 tests)
├── hero/                    # SVG hero generator
├── deploy/                  # Nginx, deployment scripts
├── docs/                    # Architecture, pitch deck, production checklist
├── docker-compose.yml       # PostgreSQL + Redis + API + Celery
├── docker-compose.prod.yml  # Production containers
├── init.sql
└── requirements.txt
```