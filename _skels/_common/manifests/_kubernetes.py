"""Shared Kubernetes Tier-2 AI manifest for Phase 7.

Dispatches on ``service.tech`` (from ``dev_skel.project.yml``) to
decide which Tier-2 files each service gets under
``deploy/helm/templates/_managed/<svc>/``.

The manifest is loaded by ``skel_ai_lib.run_kubernetes_phase``. It
intentionally ships no Python logic — consumers walk the dicts.
"""

from __future__ import annotations


DISPATCH: "dict[str, list[str]]" = {
    "python-django":      ["migration-job.yaml", "configmap.yaml", "hpa.yaml"],
    "python-django-bolt": ["migration-job.yaml", "configmap.yaml", "hpa.yaml"],
    "python-fastapi":     ["configmap.yaml", "hpa.yaml"],
    "python-flask":       ["configmap.yaml", "hpa.yaml"],
    "java-spring":        ["configmap.yaml", "hpa.yaml", "jvm-env.yaml"],
    "rust-actix":         ["configmap.yaml", "hpa.yaml"],
    "rust-axum":          ["configmap.yaml", "hpa.yaml"],
    "next-js":            ["configmap.yaml", "hpa.yaml"],
    "ts-react":           ["nginx-configmap.yaml"],
    "flutter":            [],
}


SYSTEM_PROMPT = """You are generating Kubernetes YAML for ONE service in a
multi-service Helm chart.

RULES (non-negotiable):
1. Output a valid Helm template. Use `{{ .Release.Name }}`,
   `{{ .Values.services.<svc>.* }}` where appropriate.
2. Write ONLY to `deploy/helm/templates/_managed/<svc>/<filename>`.
   Do not touch `_generated/` (Tier-1) or `overrides/` (user).
3. Never include cluster-scoped resources (Namespace,
   ClusterRole, ClusterRoleBinding, CRDs) — those are Tier-1.
4. Every resource MUST carry `metadata.labels.app.kubernetes.io/name`,
   `app.kubernetes.io/instance`, and `app.kubernetes.io/managed-by: Helm`.
5. Use `apiVersion` + `kind` that passes `kubeconform` on k8s 1.28+.
6. Output raw YAML only. No markdown fences.
"""


FILE_PROMPTS: "dict[str, str]" = {
    "migration-job.yaml": """Generate a Helm Job that runs the service's
database migrations before the Deployment is ready. Use Helm hook
annotations `helm.sh/hook: pre-install,pre-upgrade`,
`helm.sh/hook-weight: "-5"`, and
`helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded`.
The Job runs the same image as the service; command depends on tech:
- `python-django` / `python-django-bolt`: `python manage.py migrate --noinput`.
The Job MUST mount the same JWT + DATABASE_URL env vars as the
Deployment (reference them via envFrom from the service ConfigMap +
the Tier-1 `jwt-secret` Secret).
""",
    "configmap.yaml": """Generate a Helm ConfigMap named
`{{ .Release.Name }}-<svc>-config` holding the service's non-secret
env vars derived from `dev_skel.project.yml` + the wrapper `.env.example`
(everything BUT `JWT_SECRET` and `DATABASE_URL` which come from the
Tier-1 Secret and Postgres service respectively). Include at minimum
`LOG_FORMAT`, `OTEL_SERVICE_NAME`, and the service's own
`SERVICE_URL_<SLUG>`.
""",
    "hpa.yaml": """Generate a HorizontalPodAutoscaler v2 for the service.
minReplicas=1, maxReplicas=5, targetCPU=70%, targetMemory=80%. The
scaleTargetRef points at the Deployment
`{{ .Release.Name }}-<svc>` (Deployment emitted by Tier-1).
""",
    "jvm-env.yaml": """Generate a Helm ConfigMap named
`{{ .Release.Name }}-<svc>-jvm` with JVM tuning envs:
`JAVA_OPTS="-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC -XX:+HeapDumpOnOutOfMemoryError"`.
Mount into the Deployment via envFrom (the Deployment is generated
Tier-1, so reference by configmap name only — do not emit a
Deployment here).
""",
    "nginx-configmap.yaml": """Generate a Helm ConfigMap named
`{{ .Release.Name }}-<svc>-nginx` containing an `nginx.conf` key.
Serve the SPA from `/usr/share/nginx/html`, fall back to `/index.html`
for client-side routing, proxy `/api/*` to
`http://{{ .Release.Name }}-<backend>:<port>` where `<backend>` and
`<port>` are passed via Values. Include a `try_files` directive.
""",
}


FIX_PROMPT = """The previous Kubernetes generation for {service_id} failed
the cluster smoke. Here is the diagnostic bundle:

{diagnostic_bundle}

Rewrite ONLY the files under
`deploy/helm/templates/_managed/{service_id}/` to fix the failure.
Do not touch `_generated/` or `overrides/`. Output the full new
content of each file you are changing, preceded by
`===FILE: <filename>===` on its own line.
"""
