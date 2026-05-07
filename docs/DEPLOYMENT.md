# FNID Command Centre v2.0 — Deployment Guide

## Prerequisites

- Docker Engine 24.0+
- Docker Compose 2.20+
- 4GB RAM minimum (8GB recommended)
- 50GB storage minimum
- SSL certificates (production)

## Production Deployment

### Step 1: Environment Configuration

```bash
cp .env.example .env
```

Edit `.env`:
```
FNID_SECRET_KEY=<256-bit-random-key>
JWT_SECRET_KEY=<different-256-bit-key>
POSTGRES_PASSWORD=<strong-db-password>
S3_ACCESS_KEY=<jcf-s3-access>
S3_SECRET_KEY=<jcf-s3-secret>
```

### Step 2: SSL Certificates

Place certificates in `docker/nginx/ssl/`:
- `fnid.jcf.gov.jm.crt`
- `fnid.jcf.gov.jm.key`

### Step 3: Deploy

```bash
docker-compose up --build -d
```

### Step 4: Database Initialization

```bash
# Wait for postgres to be healthy
docker-compose exec -T postgres psql -U fnid_user -d fnid_db < migrations/001_initial_schema.sql

# Verify
docker-compose exec postgres psql -U fnid_user -d fnid_db -c "SELECT COUNT(*) FROM areas;"
```

### Step 5: Health Check

```bash
curl http://localhost/health
curl -H "Authorization: Bearer <token>" http://localhost/api/v1/dashboard/stats
```

## Backup & Recovery

### Automated Backup

```bash
# Daily backup cron
docker-compose exec -T postgres pg_dump -U fnid_user fnid_db | gzip > backups/fnid_$(date +%Y%m%d).sql.gz

# S3 sync
docker-compose exec app aws s3 sync /app/data/uploads s3://fnid-evidence/backups/
```

### Point-in-Time Recovery

```bash
# Restore from backup
gunzip < backups/fnid_20240101.sql.gz | docker-compose exec -T postgres psql -U fnid_user -d fnid_db
```

## Monitoring

### Prometheus Metrics
- Endpoint: `http://localhost:9090`
- Metrics: `/metrics`

### Sentry Error Tracking
- Configure `SENTRY_DSN` in `.env`

### Log Aggregation
```bash
docker-compose logs -f app
docker-compose logs -f postgres
```

## Scaling

### Horizontal Scaling
```bash
docker-compose up --scale app=3 -d
```

### Database Read Replicas
Configure in `docker-compose.yml`:
```yaml
postgres-replica:
  image: postgres:16-alpine
  # ... replication configuration
```

## Security Hardening

1. **Firewall**: Restrict port 5000 to internal network only
2. **Fail2ban**: Configure for SSH and HTTP brute force protection
3. **SELinux**: Enable on host system
4. **Updates**: Weekly `docker-compose pull && docker-compose up -d`

## Troubleshooting

### Database Connection Issues
```bash
docker-compose exec postgres pg_isready -U fnid_user
docker-compose logs postgres
```

### JWT Token Expired
Refresh token via `/auth/refresh` endpoint.

### WORM Audit Log Full
Archive old logs to S3:
```bash
docker-compose exec app python -c "from src.fnid_portal.services.audit_service import ArchiveService; ArchiveService.archive_old_logs()"
```

## Support

FNID Area 3 IT Support: it.support@fnid.jcf.gov.jm  
JCF CIB HQ: cmu.cibhq@jcf.gov.jm
