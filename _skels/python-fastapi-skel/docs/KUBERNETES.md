# Kubernetes & Helm Guide

This guide covers deploying the FastAPI DDD project to Kubernetes using raw manifests or Helm charts.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Deploy with Kustomize](#quick-deploy-with-kustomize)
- [Manual Deployment](#manual-deployment)
- [Helm Deployment](#helm-deployment)
- [Configuration](#configuration)
- [Scaling](#scaling)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Kubernetes cluster (minikube, kind, EKS, GKE, AKS, etc.)
- `kubectl` configured
- `helm` v3+ (for Helm deployments)
- Container registry access

### Local Development Clusters

```bash
# Minikube
minikube start
eval $(minikube docker-env)  # Use minikube's Docker daemon

# Kind
kind create cluster

# Docker Desktop
# Enable Kubernetes in Docker Desktop settings
```

## Quick Deploy with Kustomize

The `k8s/` directory contains Kustomize-ready manifests:

```bash
# Preview what will be deployed
kubectl kustomize k8s/

# Deploy to default namespace
kubectl apply -k k8s/

# Deploy to specific namespace
kubectl create namespace fastapi-ddd
kubectl apply -k k8s/ -n fastapi-ddd

# Delete deployment
kubectl delete -k k8s/
```

## Manual Deployment

### Step 1: Build and Push Image

```bash
# Build image
docker build -t myregistry.com/fastapi-ddd:v1.0.0 --target production .

# Push to registry
docker push myregistry.com/fastapi-ddd:v1.0.0

# For minikube (local image)
eval $(minikube docker-env)
docker build -t fastapi-ddd:latest --target production .
```

### Step 2: Create Namespace

```bash
kubectl create namespace fastapi-ddd
kubectl config set-context --current --namespace=fastapi-ddd
```

### Step 3: Create Secrets

```bash
# Create secrets from literals
kubectl create secret generic fastapi-ddd-secrets \
  --from-literal=database-url='postgresql://app:secretpass@postgres:5432/app' \
  --from-literal=secret-key='your-super-secret-key-here'

kubectl create secret generic postgres-secrets \
  --from-literal=username='app' \
  --from-literal=password='secretpass'
```

Or from file:

```bash
# Create .env.production file first
kubectl create secret generic fastapi-ddd-secrets \
  --from-env-file=.env.production
```

### Step 4: Deploy Infrastructure

```bash
# PostgreSQL
kubectl apply -f k8s/postgres.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=120s

# Redis
kubectl apply -f k8s/redis.yaml
```

### Step 5: Deploy Application

```bash
# Edit k8s/deployment.yaml to use your image
kubectl apply -f k8s/deployment.yaml

# Wait for deployment
kubectl rollout status deployment/fastapi-ddd-api
```

### Step 6: Expose Service

```bash
# For development (NodePort)
kubectl expose deployment fastapi-ddd-api --type=NodePort --port=80 --target-port=8000

# Get URL
minikube service fastapi-ddd-api --url

# For production (LoadBalancer)
kubectl expose deployment fastapi-ddd-api --type=LoadBalancer --port=80 --target-port=8000
```

### Step 7: Configure Ingress (Optional)

```bash
# Install nginx ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml

# Apply ingress
kubectl apply -f k8s/ingress.yaml
```

## Helm Deployment

### Installing the Chart

```bash
cd helm/

# Install with default values
helm install fastapi-ddd .

# Install with custom values
helm install fastapi-ddd . -f values-production.yaml

# Install to specific namespace
helm install fastapi-ddd . -n fastapi-ddd --create-namespace

# Dry run (preview)
helm install fastapi-ddd . --dry-run --debug
```

### Customizing Values

Create a `values-production.yaml`:

```yaml
replicaCount: 3

image:
  repository: myregistry.com/fastapi-ddd
  tag: v1.0.0
  pullPolicy: Always

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: api-tls
      hosts:
        - api.example.com

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80

postgresql:
  enabled: true
  auth:
    username: app
    password: secretpass
    database: app

redis:
  enabled: true
```

### Upgrading

```bash
# Upgrade with new values
helm upgrade fastapi-ddd . -f values-production.yaml

# Upgrade with specific image tag
helm upgrade fastapi-ddd . --set image.tag=v1.1.0

# Rollback
helm rollback fastapi-ddd 1
```

### Uninstalling

```bash
helm uninstall fastapi-ddd
```

## Configuration

### ConfigMaps

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fastapi-ddd-config
data:
  PROJECT_NAME: "FastAPI DDD"
  PROJECT_ENV: "production"
  SERVER_PORT: "8000"
```

Use in deployment:

```yaml
envFrom:
  - configMapRef:
      name: fastapi-ddd-config
```

### External Secrets (AWS Secrets Manager, HashiCorp Vault)

Using External Secrets Operator:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: fastapi-ddd-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: fastapi-ddd-secrets
  data:
    - secretKey: database-url
      remoteRef:
        key: fastapi-ddd/production
        property: database_url
```

## Scaling

### Manual Scaling

```bash
# Scale deployment
kubectl scale deployment fastapi-ddd-api --replicas=5

# Check pods
kubectl get pods -l app=fastapi-ddd-api
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-ddd-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-ddd-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

Apply:

```bash
kubectl apply -f hpa.yaml
kubectl get hpa
```

### Vertical Pod Autoscaler

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: fastapi-ddd-api-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-ddd-api
  updatePolicy:
    updateMode: Auto
```

## Monitoring

### Health Checks

The deployment includes liveness, readiness, and startup probes:

```yaml
livenessProbe:
  httpGet:
    path: /health/liveness
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 20

readinessProbe:
  httpGet:
    path: /health/readiness
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

startupProbe:
  httpGet:
    path: /health/liveness
    port: 8000
  initialDelaySeconds: 10
  failureThreshold: 30
  periodSeconds: 5
```

### Prometheus Metrics

Add ServiceMonitor for Prometheus Operator:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: fastapi-ddd-api
spec:
  selector:
    matchLabels:
      app: fastapi-ddd-api
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### Logging

View logs:

```bash
# All pods
kubectl logs -l app=fastapi-ddd-api

# Follow logs
kubectl logs -f deployment/fastapi-ddd-api

# Previous container (after crash)
kubectl logs deployment/fastapi-ddd-api --previous
```

For centralized logging, consider:
- Fluentd/Fluent Bit → Elasticsearch
- Loki → Grafana
- CloudWatch/Stackdriver

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl get pods
kubectl describe pod <pod-name>

# Check events
kubectl get events --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name>
```

### Common Issues

**ImagePullBackOff**:
```bash
# Check image name and registry credentials
kubectl describe pod <pod-name> | grep -A5 "Events"

# Create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=myregistry.com \
  --docker-username=user \
  --docker-password=pass
```

**CrashLoopBackOff**:
```bash
# Check logs
kubectl logs <pod-name> --previous

# Debug with shell
kubectl run debug --rm -it --image=python:3.14-slim -- bash
```

**Database Connection Failed**:
```bash
# Test from within cluster
kubectl run debug --rm -it --image=postgres:16 -- psql -h postgres -U app -d app

# Check service DNS
kubectl run debug --rm -it --image=busybox -- nslookup postgres
```

### Debugging Tools

```bash
# Port forward for local access
kubectl port-forward deployment/fastapi-ddd-api 8000:8000

# Execute command in pod
kubectl exec -it deployment/fastapi-ddd-api -- bash

# Copy files from pod
kubectl cp <pod-name>:/app/logs ./logs

# Network debugging
kubectl run netshoot --rm -it --image=nicolaka/netshoot -- bash
```

### Rolling Back

```bash
# View rollout history
kubectl rollout history deployment/fastapi-ddd-api

# Rollback to previous version
kubectl rollout undo deployment/fastapi-ddd-api

# Rollback to specific revision
kubectl rollout undo deployment/fastapi-ddd-api --to-revision=2
```

## Production Checklist

- [ ] Use specific image tags (not `latest`)
- [ ] Configure resource requests and limits
- [ ] Set up health probes
- [ ] Configure secrets properly (not in ConfigMaps)
- [ ] Enable TLS/HTTPS via Ingress
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Set up backup for PostgreSQL
- [ ] Configure network policies
- [ ] Enable pod disruption budgets
- [ ] Set up CI/CD pipeline
