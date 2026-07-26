# Production Readiness Checklist

## Pre-Deployment

### Security

- [ ] Rotate `OPENROUTER_API_KEY` or `OPENAI_API_KEY` from defaults
- [ ] Set `REQUIRE_AUTH=true` in production environment
- [ ] Set a strong `CSRF_SECRET_KEY` (generate with `uv run python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Enable SSL/TLS termination at load balancer
- [ ] Review and update `MOCK_TENANT_REGISTRY` with production API keys
- [ ] Set strong PostgreSQL password (not `securepassword123`)
- [ ] Enable Redis authentication
- [ ] Configure firewall rules (only ports 80/443 open)
- [ ] Verify `ALLOWED_ORIGINS` matches your production domain

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql://predicate_writer:password@host:5432/predicate_db
DATABASE_READONLY_URL=postgresql://predicate_reader:password@host:5432/predicate_db
REDIS_URL=redis://:password@host:6379/0

# LLM Provider (configure the one matching LLM_PROVIDER)
LLM_PROVIDER=openrouter
LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_API_KEY=sk-or-v1-...
# OR
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o-mini
# OPENAI_API_KEY=sk-...

# Security
REQUIRE_AUTH=true
CSRF_SECRET_KEY=<random-64-char-hex>
MAX_PROMPT_LENGTH=2000
QUERY_TIMEOUT_SECONDS=30
ALLOWED_ORIGINS=https://yourdomain.com

# Observability
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Database

- [ ] Run migrations: `alembic upgrade head`
- [ ] Verify indexes exist: `idx_customers_tenant`, `idx_orders_tenant`, `idx_products_tenant`
- [ ] Configure connection pool limits (minconn/maxconn)
- [ ] Set up automated backups (daily)
- [ ] Test point-in-time recovery

### Redis

- [ ] Enable `requirepass`
- [ ] Configure maxmemory policy: `allkeys-lru`
- [ ] Set maxmemory limit (e.g., `256mb`)
- [ ] Enable AOF persistence for durability

---

## Infrastructure

### Docker Compose (Production)

```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d
```

### Nginx Configuration

- [ ] SSL certificate configured
- [ ] Rate limiting applied at edge
- [ ] Proxy headers set correctly
- [ ] Static files served directly
- [ ] Gzip compression enabled

### Health Checks

- [ ] `GET /health` returns 200
- [ ] PostgreSQL container health check passes
- [ ] Redis container health check passes
- [ ] Celery worker status verified

---

## Monitoring

### Metrics to Track

| Metric | Threshold | Action |
|--------|-----------|--------|
| API Response Time | p99 > 500ms | Scale horizontally |
| Cache Hit Rate | < 70% | Review query patterns |
| Error Rate | > 1% | Investigate logs |
| CPU Usage | > 80% sustained | Add workers |
| Memory Usage | > 85% | Increase limits |
| Redis Memory | > 80% maxmemory | Evict or scale |

### Logging

- [ ] Application logs to stdout/stderr
- [ ] PostgreSQL logs configured
- [ ] Redis logs configured
- [ ] Centralized logging (ELK/Datadog) configured

### Alerting

- [ ] PagerDuty/Slack alerts for 5xx errors
- [ ] Alert on database connection failures
- [ ] Alert on Redis connection failures
- [ ] Alert on high latency

---

## Deployment Steps

### 1. Pre-deploy

```bash
# Pull latest changes
git pull origin main

# Install dependencies
uv sync

# Run migrations
alembic upgrade head
```

### 2. Deploy

```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# Verify health
curl http://localhost:8000/health
```

### 3. Post-deploy

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Verify Celery worker
docker-compose -f docker-compose.prod.yml exec celery_worker celery -A app.worker.celery_worker inspect ping
```

### 4. Rollback (if needed)

```bash
# Rollback database
alembic downgrade -1

# Restart services
docker-compose -f docker-compose.prod.yml restart
```

---

## Scaling

### Horizontal Scaling

- Add more `web_api` instances behind load balancer
- Add more `celery_worker` instances for background tasks
- Use Redis Cluster for cache layer

### Vertical Scaling

- Increase CPU/memory for PostgreSQL
- Increase Redis memory limit
- Scale Celery worker concurrency

---

## Security Checklist

- [ ] No secrets in git history
- [ ] `.env` files in `.gitignore`
- [ ] API keys rotated regularly
- [ ] `CSRF_SECRET_KEY` set and unique per environment
- [ ] `REQUIRE_AUTH=true` in production
- [ ] Database connections encrypted (SSL)
- [ ] Redis connections encrypted (SSL)
- [ ] Read-only DB role (`predicate_reader`) used for queries
- [ ] Audit logs retained for compliance period
- [ ] Rate limits enforced per tenant
- [ ] Input validation on all endpoints (MAX_PROMPT_LENGTH enforced)
- [ ] Query timeouts configured (QUERY_TIMEOUT_SECONDS)
- [ ] SQL injection prevented (parameterized queries only)
- [ ] Security headers present (X-Frame-Options, HSTS, CSP, nosniff)
- [ ] CORS locked to production domain (ALLOWED_ORIGINS)
- [ ] XSS prevention (Content-Type headers)

---

## Backup & Recovery

### Database Backups

```bash
# Manual backup
pg_dump -U postgres predicate_db > backup_$(date +%Y%m%d).sql

# Restore
psql -U postgres predicate_db < backup_20260726.sql
```

### Automated Backups

- [ ] Daily PostgreSQL dumps to S3
- [ ] 30-day retention policy
- [ ] Test restore procedure monthly

---

## Go-Live Sign-off

- [ ] All tests passing: `pytest -v` (37/37)
- [ ] CI pipeline green
- [ ] Benchmark suite passing: `uv run python benchmark.py`
- [ ] Security audit completed (see docs/threat-model.md)
- [ ] Documentation updated (README, CHANGELOG, docs/)
- [ ] Load testing completed (phase 3 of benchmark suite)
- [ ] Runbook created
- [ ] On-call rotation scheduled
