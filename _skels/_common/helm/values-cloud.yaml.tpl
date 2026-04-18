# Cloud deployment overrides (EKS / GKE / AKS).
# Usage: helm install {{PROJECT_NAME}} ./deploy/helm -f deploy/helm/values-cloud.yaml

images:
  pullPolicy: Always

ingress:
  enabled: true

postgres:
  storage: 10Gi
