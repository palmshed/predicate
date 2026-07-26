# Predicate Deployment Guide

Predicate is an open-core NL-to-SQL middleware that translates natural language prompts into parameterized SQL queries. This guide covers local development, Docker Compose, and production deployment.

---

## Table of Contents

1. [Local Development](#1-local-development)
2. [Docker Compose](#2-docker-compose)
3. [Production Deployment](#3-production-deployment)
4. [Database Setup](#4-database-setup)

---

## 1. Local Development

### Prerequisites

| Dependency  | Minimum Version |
|-------------|-----------------|
| Python      | 3.14+           |
| PostgreSQL  | 15+             |
| Redis       | 7+              |
| LLM API key | OpenRouter or OpenAI |

### Step 1: Clone and install dependencies

```bash
git clone https://github.com/palmshed/predicate.git
cd predicate

uv sync
```

### Step 3: Start PostgreSQL and Redis via Homebrew

```bash
brew services start postgresql@15
brew services start redis
```

Verify both are running:

```bash
pg_isready
redis-cli ping
```

`pg_isready` should return `accepting connections` and `redis-cli ping` should return `PONG`.

### Step 4: Create the database and load schema

```bash
createdb predicate_db
psql predicate_db < init.sql
```

This creates the `customers`, `orders`, `products`, and `audit_logs` tables, seeds sample data, and provisions the `predicate_reader` role.

### Step 5: Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at least one LLM provider key:

```
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
```

For local development, leave `REQUIRE_AUTH=false` and `ALLOWED_ORIGINS` set to localhost.

### Step 6: Start the API server

```bash
uv run uvicorn app.main:app --reload
```

### Step 7: Verify the deployment

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok"}
```

---

## 2. Docker Compose

### Prerequisites

| Dependency     | Minimum Version |
|----------------|-----------------|
| Docker         | 24+             |
| Docker Compose | v2+             |

### Step 1: Configure environment variables

```bash
cp .env.example .env
```

Set your LLM provider and API key in `.env`. The Docker Compose file reads `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`, and `OPENROUTER_API_KEY` from the host environment.

### Step 2: Build and start all services

```bash
docker-compose up --build
```

This starts four containers:

| Service        | Container Name         | Port |
|----------------|------------------------|------|
| `web_api`      | `predicate_web_api`    | 8000 |
| `postgres_db`  | `predicate_postgres`   | 5432 |
| `redis_cache`  | `predicate_redis`      | 6379 |
| `celery_worker`| `predicate_celery_worker` | -- |

The `init.sql` file is mounted into the PostgreSQL container at `/docker-entrypoint-initdb.d/init.sql`, so the schema is created automatically on first run.

### Step 3: Verify health check

```bash
curl http://localhost:8000/health
```

To view logs for a specific service:

```bash
docker-compose logs -f web_api
docker-compose logs -f celery_worker
```

To stop all services:

```bash
docker-compose down
```

To stop and remove persistent volumes:

```bash
docker-compose down -v
```

---

## 3. Production Deployment

### 3.1 Environment Variables

Create `.env.production` on the target host. All variables are read by the `web_api_prod` and `celery_worker_prod` services.

#### Required

| Variable               | Example                                                      | Description                                       |
|------------------------|--------------------------------------------------------------|---------------------------------------------------|
| `DATABASE_URL`         | `postgresql://predicate_writer:<pass>@db-host:5432/prod_db` | Read-write connection string                      |
| `DATABASE_READONLY_URL`| `postgresql://predicate_reader:<pass>@db-host:5432/prod_db` | Read-only connection for query execution          |
| `REDIS_URL`            | `redis://:<pass>@redis-host:6379/0`                          | Redis connection with authentication              |
| `REQUIRE_AUTH`         | `true`                                                       | Enforce API key validation on all endpoints       |
| `CSRF_SECRET_KEY`      | 64-character hex string                                      | Signing key for CSRF tokens                       |
| `LLM_PROVIDER`        | `openrouter` or `openai`                                     | Which LLM backend to use                          |
| `ALLOWED_ORIGINS`      | `https://app.yourdomain.com`                                 | Comma-separated list of permitted origins         |

Generate a CSRF secret key:

```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

#### Optional

| Variable               | Default                         | Description                                        |
|------------------------|---------------------------------|----------------------------------------------------|
| `LLM_MODEL`           | `nvidia/nemotron-3-super-120b-a12b:free` | Model identifier (OpenRouter) or `gpt-4o` (OpenAI) |
| `OPENAI_API_KEY`      | --                              | Required when `LLM_PROVIDER=openai`                |
| `OPENROUTER_API_KEY`  | --                              | Required when `LLM_PROVIDER=openrouter`            |
| `MAX_PROMPT_LENGTH`   | `2000`                          | Maximum characters in a user prompt                |
| `QUERY_TIMEOUT_SECONDS`| `30`                           | Seconds before a SQL query is killed               |
| `LOG_LEVEL`           | `INFO`                          | Python logging level (`DEBUG`, `INFO`, `WARNING`)  |
| `LOG_FORMAT`          | `json`                          | `json` for structured logs, `text` for human-readable |

#### LLM Provider Notes

**OpenRouter (free tier):** No credit card required. Uses models like `nvidia/nemotron-3-super-120b-a12b:free`. Set `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`.

**OpenAI:** Requires a paid API key. Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`. Update `LLM_MODEL` to a supported model like `gpt-4o`.

### 3.2 Nginx Reverse Proxy

The production Docker Compose file includes an `nginx_proxy` service that reads `deploy/nginx/predicate.conf`.

Edit the Nginx configuration to replace `yourdomain.com` with your actual domain:

```bash
sed -i 's/yourdomain.com/yourdomain.com/g' deploy/nginx/predicate.conf
```

The Nginx config provides:

- HTTP to HTTPS redirect
- TLS 1.2/1.3 with strong cipher suites
- HSTS with a 2-year max-age
- Security headers: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, `Permissions-Policy`
- Reverse proxy to `web_api_prod:8000`
- 50 MB upload limit and 600-second read timeout

### 3.3 TLS with Let's Encrypt

On the host machine (outside Docker), install Certbot and obtain certificates:

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com
```

The certificates are mounted into the Nginx container at `/etc/letsencrypt`. The paths in `predicate.conf` point to:

```
/etc/letsencrypt/live/yourdomain.com/fullchain.pem
/etc/letsencrypt/live/yourdomain.com/privkey.pem
```

Set up auto-renewal:

```bash
echo "0 0,12 * * * root certbot renew --quiet" | sudo tee /etc/cron.d/certbot-renew
```

### 3.4 Production Docker Compose

The file `docker-compose.prod.yml` defines the production stack:

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

Services started:

| Service             | Container Name              | Port Exposed |
|---------------------|-----------------------------|--------------|
| `postgres_db_prod`  | `predicate_postgres_prod`   | (internal)   |
| `redis_cache_prod`  | `predicate_redis_prod`      | (internal)   |
| `web_api_prod`      | `predicate_web_api_prod`    | (internal)   |
| `celery_worker_prod`| `predicate_celery_worker_prod` | (internal) |
| `nginx_proxy`       | `predicate_nginx_prod`      | 80, 443      |

Only Nginx is exposed externally. PostgreSQL, Redis, and the web API communicate over Docker's internal network.

### 3.5 Database Initialization

Run schema creation inside the running PostgreSQL container, or from the host:

```bash
# Option A: psql from host
psql -h localhost -U postgres -d predicate_db_prod < init.sql

# Option B: Docker exec
docker exec -i predicate_postgres_prod psql -U postgres -d predicate_db_prod < init.sql
```

For schema migrations managed by Alembic:

```bash
docker exec predicate_web_api_prod alembic upgrade head
```

### 3.6 Redis Configuration

The production Compose file enables AOF persistence. For additional hardening, create `deploy/redis/redis.conf`:

```
requirepass <your_redis_password>
maxmemory 256mb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
```

Mount it into the `redis_cache_prod` service:

```yaml
redis_cache_prod:
  image: redis:7-alpine
  command: redis-server /etc/redis/redis.conf
  volumes:
    - redis_prod_data:/data
    - ./deploy/redis/redis.conf:/etc/redis/redis.conf:ro
```

Update `REDIS_URL` in `.env.production` to include the password:

```
REDIS_URL=redis://:<password>@redis_cache_prod:6379/0
```

### 3.7 Celery Worker Startup

The `celery_worker_prod` service starts automatically with the production Compose file. The command runs with concurrency:

```bash
celery -A app.worker.celery_worker worker --loglevel=info --concurrency=4
```

Adjust `--concurrency` based on available CPU cores. A good starting point is `2 * CPU cores`.

To monitor Celery workers:

```bash
docker exec predicate_celery_worker_prod celery -A app.worker.celery_worker inspect active
docker exec predicate_celery_worker_prod celery -A app.worker.celery_worker inspect stats
```

### 3.8 Health Check Verification

After starting the production stack:

```bash
# Verify HTTP -> HTTPS redirect
curl -I http://yourdomain.com

# Verify HTTPS health endpoint
curl -I https://yourdomain.com/health

# Verify response body
curl https://yourdomain.com/health
```

Check all container statuses:

```bash
docker-compose -f docker-compose.prod.yml ps
```

All services should show `Up` status. Review logs if any container is unhealthy:

```bash
docker-compose -f docker-compose.prod.yml logs --tail=50 web_api_prod
docker-compose -f docker-compose.prod.yml logs --tail=50 postgres_db_prod
```

### 3.9 Rollback Procedure

If a deployment introduces issues, follow these steps:

**1. Stop the current stack:**

```bash
docker-compose -f docker-compose.prod.yml down
```

**2. Restore the previous Docker image.** If using a tagged image:

```bash
# Check available images
docker images | grep predicate

# Tag the known-good image
docker tag predicate_web_api:previous-good predicate_web_api:latest
```

**3. Roll back database migrations if needed:**

```bash
docker run --rm \
  --network predicate_default \
  -v $(pwd)/alembic:/app/alembic \
  -v $(pwd)/alembic.ini:/app/alembic.ini \
  -e DATABASE_URL="postgresql://predicate_writer:<pass>@postgres_db_prod:5432/prod_db" \
  predicate_web_api:latest \
  alembic downgrade -1
```

**4. Restart with the previous version:**

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

**5. Verify the rollback:**

```bash
curl https://yourdomain.com/health
docker-compose -f docker-compose.prod.yml ps
```

---

## 4. Database Setup

### 4.1 Schema Creation

Predicate provides two methods for schema initialization:

**init.sql (manual):**

```bash
psql predicate_db < init.sql
```

This creates all tables, indexes, seed data, and the `predicate_reader` role in a single pass. Suitable for fresh deployments.

**Alembic (migration-based):**

```bash
alembic upgrade head
```

Alembic tracks schema versions and applies incremental changes. Use this for environments where the schema evolves over time.

### 4.2 Read-Only Role

The `init.sql` file provisions a `predicate_reader` role with `SELECT`-only access. This role is used by `DATABASE_READONLY_URL` for query execution, separating read traffic from writes.

Grants applied:

```sql
GRANT CONNECT ON DATABASE predicate_db TO predicate_reader;
GRANT USAGE ON SCHEMA public TO predicate_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO predicate_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO predicate_reader;
```

To change the default password, update the `CREATE ROLE` statement in `init.sql` before deployment:

```sql
CREATE ROLE predicate_reader LOGIN PASSWORD 'your_secure_password_here';
```

For an existing database, update the password separately:

```sql
ALTER ROLE predicate_reader WITH PASSWORD 'your_secure_password_here';
```

### 4.3 Connection Pooling

Predicate uses `psycopg2` connection pooling via `app/database/connection.py`. The pool is configured at application startup.

Recommended settings for production:

| Parameter  | Value  | Description                          |
|------------|--------|--------------------------------------|
| `minconn`  | 5      | Minimum idle connections maintained  |
| `maxconn`  | 20     | Maximum connections per pool instance |

The read-write pool connects via `DATABASE_URL` and the read-only pool via `DATABASE_READONLY_URL`. Scale `maxconn` vertically with available RAM and PostgreSQL `max_connections`.

### 4.4 Backup Strategy

**Automated pg_dump (daily):**

```bash
# On the database host
pg_dump -U postgres predicate_db_prod | gzip > /backups/predicate_$(date +%Y%m%d).sql.gz
```

Schedule with cron:

```bash
echo "0 2 * * * pg_dump -U postgres predicate_db_prod | gzip > /backups/predicate_\$(date +\%Y\%m\%d).sql.gz" | sudo tee /etc/cron.d/predicate-backup
```

**Restore from backup:**

```bash
# Stop the application to prevent writes
docker-compose -f docker-compose.prod.yml stop web_api_prod celery_worker_prod

# Drop and recreate the database
docker exec predicate_postgres_prod dropdb -U postgres predicate_db_prod
docker exec predicate_postgres_prod createdb -U postgres predicate_db_prod

# Restore
gunzip < /backups/predicate_20260727.sql.gz | docker exec -i predicate_postgres_prod psql -U postgres -d predicate_db_prod

# Restart application
docker-compose -f docker-compose.prod.yml up -d web_api_prod celery_worker_prod
```

**Volume-level backup (Docker):**

```bash
docker run --rm \
  -v predicate_postgres_prod_data:/data \
  -v /backups:/backup \
  alpine tar czf /backup/predicate_volume_$(date +%Y%m%d).tar.gz -C /data .
```

---

## Quick Reference

| Task                     | Command                                                                  |
|--------------------------|--------------------------------------------------------------------------|
| Start local dev          | `uvicorn app.main:app --reload`                                          |
| Start Docker dev stack   | `docker-compose up --build`                                              |
| Start Docker prod stack  | `docker-compose -f docker-compose.prod.yml up --build -d`               |
| Check health             | `curl http://localhost:8000/health`                                      |
| View logs                | `docker-compose logs -f web_api`                                         |
| Run migrations           | `alembic upgrade head`                                                   |
| Generate CSRF key        | `uv run python -c "import secrets; print(secrets.token_hex(32))"`         |
| Backup database          | `pg_dump -U postgres predicate_db \| gzip > backup.sql.gz`               |
| Rollback migration       | `alembic downgrade -1`                                                   |
