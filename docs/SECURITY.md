# Security

## Authentication & Authorization

- **AuthN**: AWS Cognito user pools, OAuth2 Authorization Code + PKCE from the
  Next.js app. FastAPI validates RS256 JWTs against Cognito's JWKS (cached,
  rotated). No passwords ever touch our servers.
- **AuthZ**: RBAC with roles `owner`, `advisor`, `client_viewer`, `analyst`,
  `admin`, enforced in a FastAPI dependency (`require_role(...)`) AND via
  Postgres Row-Level Security (defense in depth — a bug in one router cannot
  leak cross-tenant rows).
- **MFA** required for `advisor`/`admin` roles (Cognito TOTP).
- **Session**: short-lived access tokens (15 min) + rotating refresh tokens
  (30 days, revocable per-device from `/users/me/sessions`).

## Data protection

- **Encryption in transit**: TLS 1.2+ everywhere (ALB, RDS, ElastiCache,
  S3), HSTS enabled on the web app.
- **Encryption at rest**: RDS (KMS), S3 (SSE-KMS, versioned + object lock on
  `statements/`), EBS volumes for ECS.
- **PII minimization**: PAN/Aadhaar (if ever collected for KYC) stored only
  as tokenized references from a dedicated KYC provider — never raw in our
  DB. Bank account numbers are never stored (Phase 1 has no payment/broker
  execution).
- **Secrets**: AWS Secrets Manager, injected as ECS task secrets; rotated
  automatically for DB credentials (RDS IAM auth as target state).
- **Field-level encryption** for `notification_prefs` phone numbers and any
  free-text chat content containing PII, using envelope encryption
  (KMS data key per organization).

## Application security (OWASP Top 10)

| Risk | Mitigation |
|---|---|
| A01 Broken Access Control | RBAC + RLS (above); every repository method takes an authenticated `Principal` and filters by it — no "trust the caller" endpoints |
| A02 Cryptographic Failures | TLS everywhere, KMS-backed encryption at rest, no custom crypto |
| A03 Injection | SQLAlchemy parameterized queries only; no raw string SQL; Pydantic input validation on every endpoint; LLM prompt inputs are templated, not string-concatenated with user text into system prompts |
| A04 Insecure Design | Threat-modeled per feature (imports = untrusted file parsing is treated as hostile input, sandboxed) |
| A05 Security Misconfiguration | Terraform-managed infra (no console drift), `SECURITY.md` reviewed each release, security headers via middleware (CSP, X-Content-Type-Options, Referrer-Policy) |
| A06 Vulnerable Components | Dependabot + `pip-audit`/`npm audit` in CI, blocks merge on critical CVEs |
| A07 Auth Failures | Cognito (battle-tested), rate-limited login, account lockout after repeated failures |
| A08 Data Integrity Failures | `import_jobs` provenance, audit log on every mutation, S3 object versioning for uploaded statements |
| A09 Logging & Monitoring Failures | Structured JSON logs → CloudWatch, alerting on auth anomalies (see `MONITORING.md`) |
| A10 SSRF | Outbound fetches (fund data providers, news) go through an allow-listed egress proxy; no user-supplied URLs are fetched server-side |

## File upload safety (statements)

- Uploads go **directly to S3** via presigned URL (never through app memory).
- Server-side: content-type sniffing (not trusting the client's declared
  type), file-size caps, antivirus scan (ClamAV Lambda triggered on
  `ObjectCreated`) before the parser touches the file, PDF parsing runs in a
  sandboxed Lambda with no network egress.

## Multi-tenancy isolation

Every query in `apps/api/app/db/repositories/*` is written against a
`Principal(organization_id, user_id, role)` and includes `WHERE
organization_id = :org_id` even though RLS would also catch a miss — tests in
`apps/api/app/tests/test_tenant_isolation.py` assert that a token for org A
can never read org B's rows via any endpoint.

## Compliance posture

- **GDPR-ready**: `/users/me/export` (data portability), `/users/me` DELETE
  (right to erasure — cascades with audit-log retention carve-out for
  financial-record legal holds), consent tracked in `users.consent_json`.
- **SEBI Investment Adviser considerations**: the product frames output as
  "analysis and recommendations for your consideration", never places trades,
  and every recommendation is evidence-backed and stored immutably —
  positioning it as a decision-support tool. **Actual regulatory
  classification (Investment Adviser registration, RIA vs. execution-only)
  must be reviewed with counsel before commercial launch in India** — this
  is a legal, not engineering, gate.
- **Audit logging**: append-only `audit_logs`, exported nightly to S3 Glacier
  for long-term, tamper-evident retention.

## Secure SDLC

- Branch protection + required review on `main`.
- `security-review` CI job (SAST via `bandit`/`semgrep` for Python,
  `eslint-plugin-security` for TS) blocks merge on high-severity findings.
- Secrets scanning (`gitleaks`) in CI and pre-commit.
- Quarterly dependency and infra access review; least-privilege IAM roles
  per ECS task (task role scoped to only the S3 prefixes/Secrets it needs).
