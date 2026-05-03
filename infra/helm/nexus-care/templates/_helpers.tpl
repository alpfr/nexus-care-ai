{{/*
Common helpers for the nexus-care chart.
*/}}

{{/*
Chart fullname — used as the prefix for all resources.
*/}}
{{- define "nexus-care.fullname" -}}
{{- default .Release.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels applied to every resource.
*/}}
{{- define "nexus-care.labels" -}}
app.kubernetes.io/name: nexus-care
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/*
Selector labels for a specific service component.
Args: { "ctx": ., "component": "api"|"platform"|"web" }
*/}}
{{- define "nexus-care.selectorLabels" -}}
app.kubernetes.io/name: nexus-care
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/*
Service account name.
*/}}
{{- define "nexus-care.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (printf "%s-sa" (include "nexus-care.fullname" .)) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Build a full image reference for a service component.
Args: { "ctx": ., "service": "api"|"platform"|"web"|"migrate" }
Joins .Values.image.registry, the service-specific repository, and tag.
*/}}
{{- define "nexus-care.image" -}}
{{- $svc := index .ctx.Values .service -}}
{{- $registry := .ctx.Values.image.registry -}}
{{- $repo := $svc.image.repository -}}
{{- $tag := .ctx.Values.image.tag -}}
{{- if $registry -}}
{{ $registry }}/{{ $repo }}:{{ $tag }}
{{- else -}}
{{ $repo }}:{{ $tag }}
{{- end -}}
{{- end -}}
