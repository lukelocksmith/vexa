# Vexa Docker Swarm Deployment Guide

This guide provides comprehensive instructions for deploying Vexa on a Docker Swarm cluster, enabling high availability, scalability, and rolling updates across multiple nodes.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Step-by-Step Deployment](#step-by-step-deployment)
- [Configuration](#configuration)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

## Overview

The Docker Swarm deployment transforms Vexa from a single-node Docker Compose setup into a distributed, production-ready system with:

- **High Availability**: Services automatically restart on failure
- **Scalability**: Horizontal scaling across multiple nodes
- **Load Balancing**: Built-in routing mesh distributes traffic
- **Rolling Updates**: Zero-downtime deployments
- **Secret Management**: Secure credential handling

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Manager Node  │    │  Worker Node 1  │    │  Worker Node 2  │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │  Postgres   │ │    │ │ API Gateway │ │    │ │WhisperLive  │ │
│ │   Redis     │ │    │ │  Admin API  │ │    │ │Transcr.Coll.│ │
│ │  Traefik    │ │    │ │             │ │    │ │             │ │
│ │Bot Manager  │ │    │ └─────────────┘ │    │ └─────────────┘ │
│ └─────────────┘ │    └─────────────────┘    └─────────────────┘
└─────────────────┘                                               
        │                        │                        │       
        └────────── Overlay Networks ──────────────────────┘       
```

## Prerequisites

### Infrastructure Requirements

- **Minimum**: 3 nodes (1 manager + 2 workers)
- **Recommended**: 5+ nodes for high availability
- **OS**: Linux with Docker Engine ≥ 24.0
- **Network**: All nodes must communicate on ports 2377, 7946, 4789
- **Storage**: Shared storage for persistent volumes (optional but recommended)

### Cloud Provider Examples

**AWS EC2:**
```bash
# Security Group Rules
Inbound:  22 (SSH), 80 (HTTP), 8085 (Traefik), 2377, 7946, 4789
Outbound: All traffic
```

**DigitalOcean Droplets:**
```bash
# Firewall Rules
SSH (22), HTTP (80), Custom (8085, 2377, 7946, 4789)
```

### Local Development

For testing, you can use a single-node swarm:
```bash
make -f Makefile.swarm swarm-init
```

## Quick Start

### 1. One-Command Deployment

```bash
# Clone the repository
git clone https://github.com/Vexa-ai/vexa
cd vexa

# Edit configuration
vim Makefile.swarm  # Change REGISTRY_USER

# Deploy everything
make -f Makefile.swarm swarm-setup
```

### 2. Access Your Deployment

```bash
# Get your manager node IP
MANAGER_IP=$(docker info --format '{{.Swarm.NodeAddr}}')

# Access the application
echo "API Documentation: http://$MANAGER_IP/docs"
echo "Traefik Dashboard: http://$MANAGER_IP:8085"
```

## Step-by-Step Deployment

### Phase 1: Cluster Setup

#### Initialize Swarm Manager

```bash
# On your designated manager node
make -f Makefile.swarm swarm-init
```

This will output a `docker swarm join` command. **Save this command!**

#### Add Worker Nodes

```bash
# On each worker node, run the join command from above
docker swarm join --token SWMTKN-... <MANAGER_IP>:2377
```

#### Verify Cluster

```bash
# On manager node
make -f Makefile.swarm swarm-nodes
```

### Phase 2: Registry Setup

#### Configure Container Registry

Choose your registry and log in:

```bash
# GitHub Container Registry (recommended)
export CR_PAT="your_github_personal_access_token"
echo $CR_PAT | docker login ghcr.io -u your-username --password-stdin

# Docker Hub
docker login

# AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
```

#### Edit Configuration

```bash
# Edit Makefile.swarm
vim Makefile.swarm

# Change these variables:
REGISTRY_USER = your-actual-username
IMAGE_TAG = 1.0.0  # or use git commit hash
REGISTRY = ghcr.io  # or your registry
```

### Phase 3: Build and Deploy

#### Build and Push Images

```bash
# Build all service images and push to registry
make -f Makefile.swarm swarm-build-and-push
```

This will build and push 7 images:
- `vexa-api-gateway`
- `vexa-admin-api`
- `vexa-bot-manager`
- `vexa-transcription-collector`
- `vexa-whisperlive-gpu`
- `vexa-whisperlive-cpu`
- `vexa-bot`

#### Configure Environment

```bash
# Update compose file with your registry settings
make -f Makefile.swarm swarm-env
```

#### Create Secrets

```bash
# Create secure passwords and tokens
make -f Makefile.swarm swarm-secrets
```

#### Deploy Stack

```bash
# Deploy to swarm
make -f Makefile.swarm swarm-deploy
```

### Phase 4: Verification

#### Check Status

```bash
# View overall status
make -f Makefile.swarm swarm-status

# Run smoke tests
make -f Makefile.swarm swarm-test
```

#### Monitor Deployment

```bash
# Watch services come online
watch "docker stack services vexa"

# Check specific service logs
make -f Makefile.swarm swarm-logs SERVICE=api-gateway
```

## Configuration

### Hardware Profiles

#### CPU-Only Deployment

Edit `docker-compose.swarm.yml`:
```yaml
# Comment out whisperlive (GPU)
# whisperlive:
#   image: ghcr.io/...

# Uncomment whisperlive-cpu
whisperlive-cpu:
  image: ghcr.io/your-user/vexa-whisperlive-cpu:1.0.0
  # ... rest of config
```

#### GPU Deployment

For GPU nodes, label them first:
```bash
# On manager node
docker node update --label-add gpu=true worker-node-1

# Edit docker-compose.swarm.yml
# Uncomment whisperlive (GPU) section
# Comment out whisperlive-cpu section
```

### Environment Variables

Set environment variables in `docker-compose.swarm.yml`:

```yaml
services:
  whisperlive-cpu:
    environment:
      - LANGUAGE_DETECTION_SEGMENTS=10
      - VAD_FILTER_THRESHOLD=0.2
      - WHISPER_MODEL_SIZE=tiny  # tiny, small, medium, large
```

### Resource Limits

Add resource constraints:

```yaml
services:
  api-gateway:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

## Operations

### Scaling Services

```bash
# Scale API Gateway to 3 replicas
docker service scale vexa_api-gateway=3

# Scale WhisperLive CPU to 4 replicas
docker service scale vexa_whisperlive-cpu=4
```

### Rolling Updates

```bash
# Build new version
make -f Makefile.swarm swarm-build-and-push IMAGE_TAG=1.1.0

# Update compose file
sed -i 's/1\.0\.0/1.1.0/g' docker-compose.swarm.yml

# Deploy update (zero downtime)
make -f Makefile.swarm swarm-deploy
```

### Monitoring

#### Service Health

```bash
# Check service status
docker service ls

# Detailed service info
docker service inspect vexa_api-gateway

# Service logs
docker service logs -f vexa_api-gateway
```

#### Node Health

```bash
# List nodes
docker node ls

# Node details
docker node inspect manager-1

# Node resource usage
docker system df
```

### Backup and Restore

#### Database Backup

```bash
# Find postgres container
POSTGRES_TASK=$(docker service ps vexa_postgres --format "{{.Name}}.{{.ID}}" | head -1)

# Create backup
docker exec $POSTGRES_TASK pg_dump -U postgres vexa > backup.sql

# Restore
cat backup.sql | docker exec -i $POSTGRES_TASK psql -U postgres vexa
```

#### Volume Backup

```bash
# Backup Redis data
docker run --rm -v vexa_redis-data:/data -v $PWD:/backup alpine tar czf /backup/redis-backup.tar.gz -C /data .

# Restore Redis data
docker run --rm -v vexa_redis-data:/data -v $PWD:/backup alpine tar xzf /backup/redis-backup.tar.gz -C /data
```

## Troubleshooting

### Common Issues

#### Services Not Starting

```bash
# Check service status
docker stack services vexa

# Look for failed tasks
docker stack ps vexa --no-trunc

# Check specific service logs
docker service logs vexa_api-gateway
```

#### Network Connectivity Issues

```bash
# Test internal connectivity
CONTAINER=$(docker ps --filter "name=vexa_api-gateway" --format "{{.ID}}" | head -1)
docker exec $CONTAINER curl http://admin-api:8001/health

# Check networks
docker network ls --filter "name=vexa"
```

#### Registry Access Problems

```bash
# Verify login
docker system info | grep -A5 "Registry Mirrors"

# Test image pull
docker pull ghcr.io/your-user/vexa-api-gateway:1.0.0
```

#### Bot Manager Docker Socket Issues

The bot-manager needs special handling:

```bash
# Ensure it's on manager nodes
docker service update --constraint-add node.role==manager vexa_bot-manager

# Check Docker socket permissions
docker exec $(docker ps --filter "name=vexa_bot-manager" -q) ls -la /var/run/docker.sock
```

### Performance Issues

#### High Memory Usage

```bash
# Check service resource usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Add memory limits
docker service update --limit-memory 512m vexa_api-gateway
```

#### Slow Transcription

```bash
# Scale WhisperLive
docker service scale vexa_whisperlive-cpu=4

# Check GPU utilization (if using GPU)
nvidia-smi
```

### Recovery Procedures

#### Service Recovery

```bash
# Force service restart
docker service update --force vexa_api-gateway

# Rollback to previous version
docker service rollback vexa_api-gateway
```

#### Node Recovery

```bash
# Drain node for maintenance
docker node update --availability drain worker-1

# Return node to active
docker node update --availability active worker-1

# Remove failed node
docker node rm worker-1
```

#### Complete Stack Recovery

```bash
# Remove stack
make -f Makefile.swarm swarm-remove

# Redeploy
make -f Makefile.swarm swarm-deploy
```

## Advanced Topics

### High Availability Setup

#### Multi-Manager Setup

```bash
# Promote workers to managers (have 3 or 5 managers total)
docker node promote worker-1 worker-2
```

#### External Load Balancer

Use cloud load balancers in front of Swarm:

```yaml
# AWS ALB targeting port 80 on all nodes
# DigitalOcean LB targeting port 80 on all nodes
```

### Security Hardening

#### TLS Certificates

```bash
# Add TLS to Traefik
# Edit docker-compose.swarm.yml:
traefik:
  command:
    - "--certificatesresolvers.letsencrypt.acme.email=your@email.com"
    - "--certificatesresolvers.letsencrypt.acme.storage=/certificates/acme.json"
    - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
```

#### Network Encryption

```bash
# Create encrypted overlay network
docker network create --driver overlay --opt encrypted vexa_secure
```

#### Secret Rotation

```bash
# Update secrets
echo "new-password" | docker secret create postgres_password_v2 -
docker service update --secret-rm postgres_password --secret-add postgres_password_v2 vexa_postgres
docker secret rm postgres_password
```

### CI/CD Integration

#### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Swarm
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Swarm
        run: |
          make -f Makefile.swarm swarm-build-and-push IMAGE_TAG=${{ github.sha }}
          ssh manager-node "cd /path/to/vexa && make -f Makefile.swarm swarm-deploy IMAGE_TAG=${{ github.sha }}"
```

### Performance Optimization

#### Resource Allocation

```yaml
# Optimize for your workload
services:
  whisperlive-cpu:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

#### Placement Strategies

```yaml
# Spread services across availability zones
services:
  api-gateway:
    deploy:
      placement:
        constraints:
          - node.labels.zone != zone1
        preferences:
          - spread: node.labels.zone
```

### Monitoring and Observability

#### Prometheus + Grafana

```yaml
# Add to docker-compose.swarm.yml
prometheus:
  image: prom/prometheus
  configs:
    - source: prometheus_config
      target: /etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
```

#### Log Aggregation

```yaml
# Add to all services
logging:
  driver: "fluentd"
  options:
    fluentd-address: "fluentd:24224"
    tag: "vexa.{{.Name}}"
```

---

## Support

For issues and questions:

- 📖 [Project Documentation](https://github.com/Vexa-ai/vexa)
- 💬 [Discord Community](https://discord.gg/Ga9duGkVz9)
- 🐛 [GitHub Issues](https://github.com/Vexa-ai/vexa/issues)

---

**Happy Swarming! 🐝** 