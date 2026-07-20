# Deployment secret files

Do not commit real secrets in this directory.

For Prometheus, create `deploy/secrets/metrics-token` at deployment time. Its exact value must match the API environment variable `METRICS_API_KEY`.

```bash
mkdir -p deploy/secrets
umask 077
printf '%s' "$METRICS_API_KEY" > deploy/secrets/metrics-token
```

Use the organisation's secret manager or deployment platform to create the file. The supplied Compose monitoring profile mounts it read-only into Prometheus.
