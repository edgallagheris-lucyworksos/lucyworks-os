# LucyWorks production deployment

This runbook creates a technically deployable LucyWorks environment. It does not itself authorise live patient-care use. The in-application production-readiness gate must remain the source of go/no-go status.

## 1. Infrastructure prerequisites

- A Linux host or managed container platform in the UK or another approved data location.
- A real DNS name controlled by the deploying organisation.
- Managed PostgreSQL is preferred. The supplied Compose database is suitable for controlled staging and shadow-mode evaluation, not a substitute for an approved managed database service.
- Outbound HTTPS access to the hospital identity provider.
- Secret management that does not store production secrets in Git or container images.
- Encrypted off-host backup storage.
- Named monitoring and incident responders.

## 2. Configuration

```bash
cp deploy/production.env.template deploy/.env.production
```

Replace every `REQUIRED_` value. Generate independent random values for the database password, monitoring key and every vendor webhook. Do not reuse credentials.

Validate before starting:

```bash
bash scripts/production-preflight.sh
```

The preflight refuses development login, runtime schema creation, the legacy test bypass, weak secrets and placeholder values.

## 3. Build and start staging

```bash
cd deploy
docker compose --env-file .env.production -f docker-compose.production.yml build
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

The migration container must complete successfully before the API starts.

Check:

```bash
curl --fail https://YOUR-DOMAIN/api/health/live
curl --fail https://YOUR-DOMAIN/api/health/ready
```

Then run:

```bash
python scripts/security-probe.py https://YOUR-DOMAIN
```

## 4. Monitoring

Create the metrics token file without a newline leak into logs:

```bash
mkdir -p deploy/secrets
umask 077
printf '%s' 'THE-METRICS-KEY-FROM-SECRET-MANAGER' > deploy/secrets/metrics-token
```

Start Prometheus alongside the main stack:

```bash
docker compose \
  --env-file deploy/.env.production \
  -f deploy/docker-compose.production.yml \
  -f deploy/docker-compose.monitoring.yml \
  up -d
```

Route Prometheus alerts into the organisation's approved paging or service-management system. The repository intentionally does not hard-code a third-party alert destination.

## 5. Backup and restore proof

Create and verify a backup:

```bash
bash scripts/production-backup.sh
```

Rehearse restore into an isolated temporary database:

```bash
export LUCYWORKS_RESTORE_CONFIRMATION='REHEARSE RESTORE'
bash scripts/restore-rehearsal.sh deploy/.env.production deploy/backups/FILE.dump
```

Upload the backup log, checksum and restore-rehearsal output as evidence against:

- `backup.automatic`
- `backup.restore`

## 6. Identity activation

Hospital IT must create the application registration and supply:

- issuer;
- JWKS endpoint;
- authorisation endpoint;
- token endpoint;
- client ID and client secret;
- redirect URI approval;
- group or application-role identifiers.

Map only approved groups to LucyWorks roles. Test at least one real account for every deployed role, one disabled account, one account without a LucyWorks role and one expired session.

## 7. Vendor onboarding

Use the files in `config/integrations/` as the normalised LucyWorks contracts. For each vendor:

1. Obtain real sample payloads with personal data removed.
2. Map the vendor fields to the LucyWorks canonical fields.
3. Validate identity matching and duplicate handling.
4. Test invalid signatures, replayed events, corrected results and unmatched records.
5. Record the mapping profile, test report and accountable owner in `/production-readiness`.

## 8. Controlled progression

The required order is:

1. Synthetic simulation
2. Historical replay with de-identified exports
3. Live shadow mode with no operational authority
4. Bounded service-line pilot with a documented rollback
5. Reviewed scale-up

The system must not be represented as live-authorised while `/production-readiness` reports `Not authorised`.

## 9. Rollback

A pilot rollback means:

- stop creating new LucyWorks operational commands;
- retain all existing evidence and audit records;
- return operational authority to the existing hospital process;
- preserve integration envelopes for reconciliation;
- document the trigger, impact and decision owner;
- restore service only after the relevant observation is resolved and retested.
