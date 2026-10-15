# Sanaap DMS Backend

A modular-monolith Document Management System built with Django REST Framework.
It provides private MinIO storage, JWT authentication, role-based access control,
asynchronous document finalization, durable audit records, and WebSocket
notifications.

## Scope and non-goals

The service manages users and common business documents (PDF, JPEG, PNG, DOCX,
XLSX, PPTX, TXT and CSV). It intentionally does not implement public sharing,
OCR, previews, workflow management, document version history, multi-tenancy,
microservices, Kafka, RabbitMQ or antivirus infrastructure.

## Architecture

```text
browser/client -> Nginx -> Django ASGI (DRF + Channels)
                              |       |       |
                         PostgreSQL Redis   MinIO
                                      |
                                  Celery worker
```

- `apps/users`: custom `AbstractUser`, JWT endpoints, user administration and
  Django Group-based roles.
- `apps/documents`: document API, authorized selectors, validation, MinIO
  adapter, Celery tasks and WebSocket notifications.
- `apps/audit`: append-oriented document audit log.
- `apps/common`: small shared API concerns only.
- `config`: environment settings, ASGI routing and Celery bootstrap.

## Technology stack

Python 3.11, Django 5.2, DRF, PostgreSQL 16, Redis 7, Celery, MinIO/S3,
Django Channels, SimpleJWT, django-filter, drf-spectacular, Uvicorn, Nginx,
pytest and Docker Compose.

## Configuration

Copy the example and replace every placeholder:

```bash
cp .env.example .env
```

The example documents Django, PostgreSQL, three separate Redis URLs, internal
and public MinIO endpoints, JWT lifetimes, upload limit and presigned-link TTL.
The internal MinIO endpoint is used by containers. The public endpoint is
embedded in presigned URLs and must be reachable by the user's browser. In
production it must use HTTPS with a valid certificate.

`DOCUMENT_MAX_UPLOAD_SIZE` is bytes and defaults to 20 MiB. Nginx's
`client_max_body_size` is also 20 MiB; keep both aligned if changing the limit.

## Docker setup

```bash
docker compose up --build
```

Services are `postgres`, `redis`, `minio`, `minio_init`, `migrate`, `web`,
`celery_worker` and `nginx`. PostgreSQL, Redis and MinIO use named volumes.
`minio_init` idempotently creates a private bucket. `migrate` applies migrations,
initializes roles and collects static files before the web and worker services
start. Migrations are not run by each web process.

The Compose file pins the final freely available Bitnami legacy MinIO release
because the upstream community container repositories became unavailable in
2026. Mirror this immutable image into an organization-controlled registry for
production and review the storage-vendor lifecycle before a long-lived rollout.

Create the initial maintenance superuser explicitly:

```bash
docker compose run --rm web python manage.py createsuperuser
```

The role bootstrap is idempotent and can be rerun with:

```bash
docker compose run --rm web python manage.py initialize_roles
```

Local endpoints:

- API and Swagger through Nginx: `http://localhost/api/v1/`
- MinIO S3 endpoint: `http://localhost:9000`
- MinIO console: `http://localhost:9001`

## Authentication

```text
POST /api/v1/auth/token/
POST /api/v1/auth/token/refresh/
POST /api/v1/auth/logout/
GET  /api/v1/users/me/
```

Use `Authorization: Bearer <access-token>`. Access tokens default to 15 minutes;
refresh tokens default to seven days and rotate. Logout blacklists the submitted
refresh token. There is no public registration endpoint.

## User API and RBAC

```text
GET   /api/v1/users/                 Admin only
POST  /api/v1/users/                 Admin only
PATCH /api/v1/users/{id}/role/       Admin only
```

Every ordinary API-created user belongs to exactly one of `Admin`, `Editor` or
`Viewer`. A superuser is treated as Admin.

| Operation | Admin | Editor | Viewer |
|---|---|---|---|
| List/retrieve/download documents | All | Own only | All |
| Create documents | Yes | Yes | No |
| Update documents | All | Own only | No |
| Delete documents | All | No | No |
| Manage users and roles | Yes | No | No |

Document access is enforced both by an authorized QuerySet and action/object
permissions. An out-of-scope identifier returns 404. Clients cannot set owner.

## Document API

```text
GET    /api/v1/documents/
POST   /api/v1/documents/
GET    /api/v1/documents/{uuid}/
PUT    /api/v1/documents/{uuid}/
PATCH  /api/v1/documents/{uuid}/
DELETE /api/v1/documents/{uuid}/
GET    /api/v1/documents/{uuid}/download/
```

Uploads and file replacements use multipart fields `title` and `file`. Create
and file replacement return 202; metadata-only updates return 200. List results
are paginated and ordered by `-created_at,-id`. Supported filtering includes
title, MIME type, owner, status and created/updated date ranges. Search supports
title and original filename.

### Upload lifecycle

1. The API checks size, extension, magic MIME and Office container structure.
2. It writes the binary under an unguessable `staging/` key in the private bucket.
3. Metadata and `CREATE_REQUESTED` audit are committed as `PENDING`.
4. An on-commit callback sends only document/operation identifiers to Celery.
5. The worker copies to a deterministic final key, verifies size and SHA-256
   object metadata, atomically marks the row `READY`, deletes staging, writes the
   completion audit and emits `document_created`.

Tasks use operation IDs and deterministic destinations, making replay and a
crash after copy safe. Transient infrastructure failures use exponential retry
with jitter. Permanent verification failures mark creation `FAILED`.

During replacement, the existing `READY` object remains the active download.
Only after the new object is verified does the worker atomically switch the DB
key and remove the previous object. A stale replacement task cannot overwrite a
newer operation.

Delete is Admin-only and returns 202. The row enters `DELETING`; the worker
removes final/staging objects and then hard-deletes the row. Audit snapshots are
retained.

## Secure downloads

The bucket has no anonymous access. The download action verifies RBAC and READY
state, then returns a presigned GET URL (60 seconds by default). Object keys and
credentials are never serialized. Possession of a presigned URL grants access
until expiry, so HTTPS, short TTL and avoiding URL logging are essential.

The audit action is honestly named `DOWNLOAD_LINK_ISSUED`; because the transfer
goes directly to MinIO, Django cannot prove that the client completed it.

## Audit logging

The database records create/update/delete requested and completed events,
retrieval, download-link issuance and denied object actions. Actor and document
snapshot fields preserve identity after related rows are removed. Audit entries
have no public mutation endpoint and are read-only in Django Admin.

Application logging is separate and must never contain passwords, JWTs, MinIO
secrets, WebSocket tickets or presigned URLs.

## Redis and Celery

- DB 1: Django cache (`user-profile:{id}`, 60 seconds)
- DB 2: Celery broker
- DB 3: Channels layer

Profile cache is invalidated on role change. Authorization decisions, document
lists, tokens and signed URLs are never cached.

No Celery Beat service is needed. Reconcile staging objects manually:

```bash
docker compose run --rm web python manage.py cleanup_staging --dry-run
docker compose run --rm web python manage.py cleanup_staging --older-than-hours 24
```

## WebSocket authentication and events

Obtain a one-time, 30-second opaque ticket using JWT:

```text
POST /api/v1/ws-ticket/
```

Then connect once to:

```text
ws://localhost/ws/notifications/?ticket=<ticket>
```

Production must use `wss://`. Ticket consumption uses Redis `GETDEL`; expired,
replayed and inactive-user connections are rejected. Allowed-host origin
validation wraps the WebSocket application. Messages contain only:

```json
{"event":"document_created","message":"A new document has been uploaded."}
```

or `document_updated`; no document metadata is broadcast.

## OpenAPI

- Schema: `GET /api/v1/schema/`
- Swagger UI: `GET /api/v1/docs/`

## Development and tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements/local.txt
pytest
ruff check .
ruff format --check .
python manage.py check
python manage.py makemigrations --check --dry-run
```

Database/service tests should run against PostgreSQL. Unit tests mock MinIO;
Docker smoke verification exercises actual PostgreSQL, Redis, MinIO, Celery,
Nginx and WebSockets.

## Production notes

- Use unique high-entropy Django, PostgreSQL and MinIO secrets.
- Terminate TLS at Nginx or an upstream trusted proxy and use HTTPS/WSS only.
- Set exact allowed hosts, origins, CSRF and CORS values.
- Do not expose the MinIO console publicly.
- Back up PostgreSQL and MinIO together according to a documented recovery point.
- Run migrations as an explicit one-shot deployment step before application
  processes.
- Scale Uvicorn/Celery only after measuring workload; no load balancer topology is
  included in this assignment.

## Troubleshooting

- A document stuck in PENDING usually indicates the Celery worker or Redis broker
  is unavailable; inspect worker logs and safely replay the operation.
- A presigned URL containing `minio:9000` means `MINIO_PUBLIC_ENDPOINT` is wrong.
- A 404 for a known UUID may be an intentional RBAC result.
- WebSocket 4401 means the ticket is invalid, expired, reused or belongs to an
  inactive user. An invalid Origin is rejected before the consumer.
- MIME mismatch means the file bytes do not match its extension.

## Known security limitations

No antivirus engine is included by design. Magic-byte and Office-container
validation reduce spoofing but do not prove that a valid document is benign.
Presigned URLs remain bearer capabilities until expiration. Successful direct
object transfer is not observable by Django without separate MinIO/Nginx access
log processing, which is outside this scope.
