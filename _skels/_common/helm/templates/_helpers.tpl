{{/*
Expand the name of the chart.
*/}}
{{- define "devskel.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "devskel.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "devskel.labels" -}}
helm.sh/chart: {{ include "devskel.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ include "devskel.name" . }}
{{- end }}

{{/*
Selector labels for a service
*/}}
{{- define "devskel.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .release }}
{{- end }}

{{/*
Build an image reference with optional registry prefix.
Follows the swarm_digital_twin pattern: empty registry = local image.
*/}}
{{- define "devskel.image" -}}
{{- $registry := .registry -}}
{{- if $registry -}}
{{ $registry }}/{{ .name }}:{{ .tag }}
{{- else -}}
{{ .name }}:{{ .tag }}
{{- end -}}
{{- end }}
