# Enterprise Deployment Blueprint

Production cloud architecture for scaling Predicate beyond single-server deployments.

## Enterprise Cloud Architecture Mapping

```
                 [ Internet Traffic / Client Dashboards ]
                                    |
                                    v
                     [ Cloud Load Balancer (HTTPS) ]
                                    |
           +------------------------+------------------------+
           v                                                 v
[ Availability Zone A ]                           [ Availability Zone B ]
  |-- Web API Instance (EC2/ECS)                    |-- Web API Instance (EC2/ECS)
  +-- Celery Background Worker                      +-- Celery Background Worker
           |                                                 |
           +------------------------+------------------------+
                                    v
                [ Managed In-Memory Cache (Redis Cluster) ]
                                    |
                                    v
                [ Multi-AZ Relational Database Engine ]
                  |-- Primary Master Database (Writes)
                  +-- Synchronous Read Replica (AZ-B Backup)
```

## Cloud Provider Implementation Matrix

| Repository Component | AWS Solution | GCP Solution | Purpose |
|---|---|---|---|
| `web_api` | ECS (Fargate) or EKS | Cloud Run or GKE | Serverless container orchestration scaling horizontally on CPU demand. |
| `celery_worker` | ECS (Fargate Task) | Cloud Run Jobs / GKE Pool | Dedicated worker containers pulling long-running CSV export tasks. |
| `redis_cache` | ElastiCache for Redis | Memorystore for Redis | High-availability managed in-memory tier for sub-2ms query replays and rate-limiting. |
| `postgres_db` | RDS for PostgreSQL | Cloud SQL for PostgreSQL | Managed relational database with automated backups and multi-zone failover. |
| Secrets | AWS Secrets Manager | Secret Manager | Encrypted injection of `OPENAI_API_KEY` directly into runtime memory. |

## Enterprise Security Hardening Protocol

To pass SOC 2 Type II or institutional vendor evaluations, implement three structural network boundaries:

### 1. VPC Isolation

Place core managed components (PostgreSQL and Redis) inside isolated Private Subnets. No public IP addresses. Reject all inbound traffic from outside the container cluster network.

### 2. Asymmetric Security Groups

| Layer | Exposed Ports | Source |
|---|---|---|
| Load Balancer | 80, 443 | Public internet |
| FastAPI Containers | 8000 | Load Balancer only |
| PostgreSQL | 5432 | FastAPI + Celery containers only |
| Redis | 6379 | FastAPI + Celery containers only |

### 3. Data Encryption

- **In Transit:** SSL/TLS termination at Load Balancer tier using managed cloud certificates.
- **At Rest:** Hardware-level volume encryption (AES-256) on all block storage attached to PostgreSQL instances.

## Infrastructure Checklist

- [ ] VPC with public and private subnets across 2+ AZs
- [ ] NAT Gateway for outbound traffic from private subnets
- [ ] Application Load Balancer with HTTPS listener
- [ ] ECS Fargate / Cloud Run services for web_api and celery_worker
- [ ] ElastiCache / Memorystore Redis cluster (multi-AZ)
- [ ] RDS / Cloud SQL PostgreSQL with automated backups
- [ ] Secrets Manager for API keys and credentials
- [ ] CloudWatch / Cloud Monitoring for logs and alerts
- [ ] CI/CD pipeline via GitHub Actions (already configured)