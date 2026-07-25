# Novera Backend

FastAPI and PostgreSQL backend for the Novera field-operations platform.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Interactive API documentation is available at `/docs` in development.

## Tests

```powershell
python -m pytest -q
```

PostgreSQL integration tests require a migrated disposable database. Temporarily point both migration and test settings at that database:

```powershell
$originalDatabaseUrl = $env:DATABASE_URL
$env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/novera_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
alembic upgrade head
python -m pytest -q
$env:DATABASE_URL = $originalDatabaseUrl
Remove-Item Env:TEST_DATABASE_URL
```

Never point `TEST_DATABASE_URL` at a production or shared application database.

## Continuous integration

`.github/workflows/backend-ci.yml` runs on backend changes pushed to `main` or `feat/authentication`, and on pull requests targeting `main`.

The workflow starts disposable PostgreSQL, validates dependencies, compiles the code, applies the full migration chain, seeds access control, checks model-to-migration alignment, runs the complete PostgreSQL-backed suite, and builds the production image.

Keep the workflow green before merging into `main`.

## Production configuration

Set at least the following values through the deployment platform's secret and environment configuration:

```text
APP_ENV=production
DEBUG=false
ENABLE_API_DOCS=false
LOG_LEVEL=INFO
LOG_JSON=true
DATABASE_URL=postgresql+psycopg2://...
SECRET_KEY=<cryptographically-random-value-of-at-least-32-characters>
CORS_ORIGINS=["https://app.example.com"]
EMAIL_PROVIDER=smtp
EMAIL_FROM_EMAIL=no-reply@example.com
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=...
EMAIL_SMTP_PASSWORD=...
EMAIL_SMTP_USE_STARTTLS=true
EMAIL_SMTP_USE_SSL=false
```

Staging and production startup fails fast when insecure secrets, debug mode, localhost/wildcard/non-HTTPS CORS origins, a non-PostgreSQL database, or the development email provider are configured.

## Release sequence

Run migrations as an explicit release step before starting or replacing application instances:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Do not run concurrent migration commands from every application replica.

## Docker

Build from the `backend` directory:

```bash
docker build -t novera-backend .
```

Run migrations with the production environment supplied:

```bash
docker run --rm --env-file .env.production novera-backend alembic upgrade head
```

Start the API:

```bash
docker run --rm --env-file .env.production -p 8000:8000 novera-backend
```

The image runs as a non-root user and exposes a root-endpoint health check.

## Local release simulation

Docker Compose can verify the production image against disposable PostgreSQL without touching the development database:

```powershell
python .\scripts\release_smoke.py
```

The release smoke test builds the current image, applies all migrations in a one-shot container, starts the API with production safeguards, validates the root response, confirms the documentation endpoints are unavailable, and removes the temporary containers and database afterward.

`compose.release.yml` contains local smoke-test credentials only. Real deployment secrets must remain in the deployment platform.
