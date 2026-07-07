{{/*
_helpers.tpl — common template helpers for log-analyzer chart
*/}}

{{- define "log-analyzer.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "log-analyzer.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "log-analyzer.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "log-analyzer.labels" -}}
helm.sh/chart: {{ include "log-analyzer.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "log-analyzer.selectorLabels" -}}
app.kubernetes.io/name: {{ include "log-analyzer.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
