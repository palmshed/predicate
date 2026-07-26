# Operations Guide

Day-to-day operational reference for Predicate deployments.

## 1. Health Checks

### Application Endpoints

**Liveness probe:**

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "healthy",
  "version": "1.4.2",
  "git_commit": "a1b2c3d",
  "build_date": "2026-07-20T14:30:00Z",
  "uptime_seconds": 86400,
  "memory_rss_mb": 128.5,
  "pid": 1,
  "llm_provider": "openrouter",
  "llm_key_configured": true
}
```

**Readiness probe:**

```bash
curl http://localhost:8000/ready
```

Returns 200 when all dependencies (PostgreSQL, Redis) are reachable. Returns 503 with a JSON body listing failed checks.

### Docker Health Checks

The `docker-compose.yml` includes built-in health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 15s
```

Verify Docker health status:

```bash
docker inspect --format='{{.State.Health.Status}}' predicate-api
```

### Kubernetes Probes

Deployment manifest configuration:

```yaml
containers:
  - name: predicate-api
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 30
      timeoutSeconds: 5
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 2
```

Apply and verify:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl describe pod -l app=predicate-api
kubectl get events --field-selector involvedObject.name=predicate-api
```

## 2. Monitoring

### Prometheus Metrics

```bash
curl http://localhost:8000/metrics
```

Returns metrics in Prometheus exposition format.

### Key Metrics

| Metric | Type | Description |
|---|---|---|
| `requests_total` | Counter | Total HTTP requests |
| `compile_duration_milliseconds` | Histogram | NL-to-SQL compile latency |
| `validate_duration_milliseconds` | Histogram | SQL validation latency |
| `cache_hits` | Counter | Query cache hits |
| `cache_misses` | Counter | Query cache misses |
| `active_executions` | Gauge | Concurrent SQL executions |
| `validation_failures` | Counter | SQL validation rejections |
| `compile_duration_by_provider_milliseconds` | Histogram | Compile latency per LLM provider |

### Tenant-Level Metrics

```bash
curl -H "Authorization: Bearer <api-key>" http://localhost:8000/api/v1/metrics
```

Response:

```json
{
  "total_requests": 15420,
  "cache_hits": 9800,
  "db_misses": 5620,
  "rpm": 42
}
```

### Alerting Thresholds

| Metric | Warning | Critical | Action |
|---|---|---|---|
| `compile_duration_milliseconds` p99 | > 5000ms | > 15000ms | Check LLM provider latency |
| `validation_failures` rate | > 5% of requests | > 20% of requests | Review prompt patterns |
| `cache_misses` rate | > 80% | > 95% | Check Redis connectivity, review TTL |
| `active_executions` | > 50 | > 90 | Scale workers or add rate limiting |
| `requests_total` error rate (5xx) | > 1% | > 5% | Check logs, database, Redis |
| Memory RSS | > 512 MB | > 1024 MB | Investigate memory leak, restart |

## 3. Logging

### Format

Predicate emits structured JSON logs when `LOG_FORMAT=json` (default in production):

```json
{
  "ts": "2026-07-27T10:30:45.123Z",
  "level": "INFO",
  "logger": "predicate.api.compile",
  "msg": "compile completed",
  "request_id": "req_a1b2c3d4e5",
  "tenant_id": "tenant_acme"
}
```

Fields:

| Field | Description |
|---|---|
| `ts` | ISO 8601 timestamp |
| `level` | Log level |
| `logger` | Logger name (module path) |
| `msg` | Human-readable message |
| `request_id` | Unique request identifier |
| `tenant_id` | Tenant identifier (when authenticated) |

### Log Levels

| Level | When to Use |
|---|---|
| `DEBUG` | Development only. SQL compilation steps, cache operations, LLM prompts/responses |
| `INFO` | Normal operations. Request completion, cache hits, background task status |
| `WARNING` | Recoverable issues. Slow queries, cache misses, degraded dependencies |
| `ERROR` | Failures requiring attention. LLM timeouts, database errors, validation failures |

Set via `LOG_LEVEL` environment variable:

```bash
export LOG_LEVEL=INFO
```

### Request ID Correlation

Every request generates a `request_id`. Pass one explicitly via header:

```bash
curl -H "X-Request-ID: my-trace-id-123" http://localhost:8000/api/v1/compile
```

The `request_id` appears in all log lines for that request and is returned in the response header.

### Centralized Logging

**ELK Stack:**

```yaml
# Filebeat configuration
filebeat.inputs:
  - type: container
    paths:
      - "/var/lib/docker/containers/predicate-api/*.log"
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["http://elasticsearch:9200"]
  index: "predicate-logs-%{+yyyy.MM.dd}"
```

**Datadog:**

```bash
# Install Datadog Agent
helm install datadog/datadog \
  --set datadog.apiKey=<YOUR_API_KEY> \
  --set datadog.logs.enabled=true \
  --set datadog.logs.config[0].name=predicate \
  --set datadog.logs.config[0].file=/var/log/predicate/*.log
```

Verify log ingestion:

```bash
# ELK
curl http://elasticsearch:9200/predicate-logs-*/_search?size=5

# Datadog
curl -X POST "https://api.datadoghq.com/api/v1/events" \
  -H "DD-API-KEY: <YOUR_API_KEY>" \
  -d '{"query": "service:predicate-api"}'
```

## 4. Request Tracing

### TraceContext Structure

Every compile request produces a trace with named spans:

```
TraceContext
  +-- span: compile          (NL prompt -> SQL generation)
  +-- span: cache_lookup     (Redis lookup)
  +-- span: validate         (SQL safety validation)
  +-- span: execute          (SQL execution against target DB)
```

### Retrieving Traces

The trace is included in the compile response body:

```json
{
  "sql": "SELECT ...",
  "trace": {
    "request_id": "req_a1b2c3d4e5",
    "spans": [
      {"name": "compile", "start_ms": 0, "duration_ms": 1200},
      {"name": "cache_lookup", "start_ms": 1200, "duration_ms": 15},
      {"name": "validate", "start_ms": 1215, "duration_ms": 8}
    ],
    "total_duration_ms": 1223
  }
}
```

### Correlating with Logs

Use `X-Request-ID` to link traces to log lines:

```bash
# Get request ID from response header
REQUEST_ID=$(curl -sD - http://localhost:8000/api/v1/compile \
  -H "Authorization: Bearer <key>" \
  -d '{"prompt": "show me all users"}' | grep -i x-request-id | awk '{print $2}' | tr -d '\r')

# Search logs for that request
grep "$REQUEST_ID" /var/log/predicate/*.log
```

## 5. Common Failure Modes

| Symptom | Cause | Resolution |
|---|---|---|
| Connection refused on port 8000 | Server not running | Check uvicorn process: `ps aux \| grep uvicorn`. Start with `uvicorn predicate.api.main:app --host 0.0.0.0 --port 8000` |
| 401 Unauthorized | Auth enabled without valid key | Verify `REQUIRE_AUTH=true`. Ensure client sends `Authorization: Bearer <valid-key>`. Check `MOCK_TENANT_REGISTRY` |
| 403 Forbidden | Invalid API key or CSRF mismatch | Verify API key exists in `MOCK_TENANT_REGISTRY`. Check `CSRF_SECRET_KEY` consistency across instances |
| 422 Unprocessable Entity | Prompt exceeds `MAX_PROMPT_LENGTH` | Shorten the natural language prompt. Default limit is 2000 characters. Adjust via `MAX_PROMPT_LENGTH` env var |
| 500 Internal Server Error | Database connection failed | Check `DATABASE_URL`. Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`. Check connection pool settings |
| High cache miss rate | Redis not running or small TTL | Check Redis: `redis-cli ping`. Verify `REDIS_URL`. Review `CACHE_TTL_SECONDS` configuration |
| Slow query responses | LLM provider latency | Check `LLM_PROVIDER` and API key validity. Monitor network latency to provider. Consider switching providers or enabling caching |
| Audit sink failed | PostgreSQL connection issue | Non-critical. Check `audit_logs` table: `SELECT count(*) FROM audit_logs`. Verify database connectivity for audit writer |

## 6. Backup and Recovery

### PostgreSQL

**Create backup:**

```bash
pg_dump -h localhost -U predicate_writer -d predicate_db \
  -F c -Z 9 -f /backups/predicate_$(date +%Y%m%d_%H%M%S).dump
```

**Restore backup:**

```bash
pg_restore -h localhost -U predicate_writer -d predicate_db \
  --clean --if-exists /backups/predicate_20260727_103000.dump
```

**Automated daily backup script (`/etc/cron.d/predicate-backup`):**

```bash
0 2 * * * root /usr/local/bin/predicate-backup.sh >> /var/log/predicate-backup.log 2>&1
```

**Backup script (`/usr/local/bin/predicate-backup.sh`):**

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/backups/predicate"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATABASE_URL="${DATABASE_URL:?}"

mkdir -p "$BACKUP_DIR"

pg_dump "$DATABASE_URL" -F c -Z 9 -f "$BACKUP_DIR/predicate_${TIMESTAMP}.dump"

find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: predicate_${TIMESTAMP}.dump"
```

### Redis

**RDB persistence (default):**

```bash
# Trigger manual save
redis-cli -a <password> BGSAVE

# Verify dump.rdb exists
ls -la /var/lib/redis/dump.rdb
```

**AOF persistence (recommended for production):**

```conf
# redis.conf
appendonly yes
appendfsync everysec
```

**Backup Redis:**

```bash
redis-cli -a <password> BGSAVE
cp /var/lib/redis/dump.rdb /backups/redis/dump_$(date +%Y%m%d).rdb
```

### Recovery Procedure

1. Stop application services.
2. Restore PostgreSQL from latest dump.
3. Restore Redis from RDB/AOF.
4. Run `alembic upgrade head` to ensure schema is current.
5. Start application services.
6. Verify health: `curl http://localhost:8000/health`.
7. Verify readiness: `curl http://localhost:8000/ready`.

## 7. Upgrading

### Standard Upgrade

```bash
# 1. Pull latest changes
cd /opt/predicate
git fetch origin main
git checkout main
git pull origin main

# 2. Update dependencies
uv sync

# 3. Run database migrations
alembic upgrade head

# 4. Restart services
docker compose restart predicate-api
# or for systemd:
sudo systemctl restart predicate-api

# 5. Verify
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Kubernetes Upgrade

```bash
kubectl set image deployment/predicate-api \
  predicate-api=predicate/api:latest

kubectl rollout status deployment/predicate-api
```

### Rollback Procedure

**Docker Compose:**

```bash
# Revert to previous image tag
git checkout <previous-tag>
docker compose up -d --build

# Rollback database if needed
alembic downgrade -1
```

**Kubernetes:**

```bash
# Rollback to previous revision
kubectl rollout undo deployment/predicate-api

# Check rollback status
kubectl rollout status deployment/predicate-api
```

## 8. Scaling

### Horizontal Scaling

Add web API instances behind a load balancer:

```yaml
# docker-compose.yml
services:
  predicate-api-1:
    image: predicate/api:latest
    ports:
      - "8001:8000"
  predicate-api-2:
    image: predicate/api:latest
    ports:
      - "8002:8000"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

**Nginx load balancing config:**

```nginx
upstream predicate {
    least_conn;
    server predicate-api-1:8000;
    server predicate-api-2:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://predicate;
        proxy_set_header X-Request-ID $request_id;
    }
}
```

### Vertical Scaling

Increase PostgreSQL resources:

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: 8G
```

### Redis Cluster

For cache-heavy deployments:

```bash
# Create 6-node Redis cluster (3 masters, 3 replicas)
redis-cli --cluster create \
  10.0.0.1:6379 10.0.0.2:6379 10.0.0.3:6379 \
  10.0.0.4:6379 10.0.0.5:6379 10.0.0.6:6379 \
  --cluster-replicas 1 -a <password>

# Verify cluster
redis-cli --cluster check 10.0.0.1:6379 -a <password>
```

Update `REDIS_URL` to use cluster mode:

```
REDIS_URL=redis://:password@10.0.0.1:6379?cluster=true
```

### Celery Worker Concurrency

Scale background task processing:

```bash
# Increase worker concurrency
celery -A predicate.worker worker \
  --loglevel=info \
  --concurrency=8 \
  --max-tasks-per-child=1000

# Or run multiple worker processes
celery -A predicate.worker worker --loglevel=info --concurrency=4 -n worker1
celery -A predicate.worker worker --loglevel=info --concurrency=4 -n worker2
```

Monitor worker status:

```bash
celery -A predicate.worker inspect active
celery -A predicate.worker inspect stats
celery -A predicate.worker inspect reserved
```
