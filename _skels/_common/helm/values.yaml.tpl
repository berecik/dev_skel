# Default values for {{PROJECT_NAME}}.
# Override with values-local.yaml or values-cloud.yaml.

images:
  repository: "{{IMAGE_REPOSITORY}}"
  tag: "latest"
  pullPolicy: IfNotPresent

namespace: "{{KUBE_NAMESPACE}}"

# Per-service configuration — auto-generated from dev_skel.project.yml.
# Each service gets a Deployment + Service + optional Ingress.
services:
{{SERVICES_VALUES}}

# Shared database (Postgres)
postgres:
  enabled: true
  image: postgres:16-alpine
  storage: 1Gi
  credentials:
    user: devskel
    password: devskel
    database: devskel

# Ingress — enable for cloud deployments
ingress:
  enabled: false
  className: nginx
  host: "{{PROJECT_NAME}}.local"
  tls: false
