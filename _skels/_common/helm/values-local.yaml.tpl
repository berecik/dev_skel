# Local development overrides (minikube / kind / Docker Desktop).
# Usage: helm install {{PROJECT_NAME}} ./deploy/helm -f deploy/helm/values-local.yaml

images:
  repository: ""
  pullPolicy: Never

postgres:
  storage: 256Mi
