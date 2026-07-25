"""Regression tests for CI and container release assets."""
from __future__ import annotations
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_ROOT.parent
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "backend-ci.yml"
COMPOSE_PATH = BACKEND_ROOT / "compose.release.yml"
DOCKERFILE_PATH = BACKEND_ROOT / "Dockerfile"
RELEASE_SCRIPT_PATH = BACKEND_ROOT / "scripts" / "release_smoke.py"

def read(path: Path) -> str:
    assert path.is_file(), f"Missing release asset: {path}"
    return path.read_text(encoding="utf-8")

def test_ci_runs_database_migrations_and_complete_suite() -> None:
    workflow = read(WORKFLOW_PATH)
    for fragment in {"postgres:17-alpine", "alembic upgrade head", "python -m app.scripts.seed_access_control", "alembic check", "python -m pytest -q", "docker build --tag novera-backend:ci ./backend"}:
        assert fragment in workflow

def test_ci_has_restricted_permissions_and_concurrency() -> None:
    workflow = read(WORKFLOW_PATH)
    assert "permissions:\n  contents: read" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "pull_request:" in workflow
    assert "branches:\n      - main" in workflow

def test_release_compose_uses_production_safeguards() -> None:
    compose = read(COMPOSE_PATH)
    for fragment in {"APP_ENV: production", 'DEBUG: "false"', 'ENABLE_API_DOCS: "false"', 'LOG_JSON: "true"', "EMAIL_PROVIDER: manual", "condition: service_healthy", "alembic", "upgrade", "head"}:
        assert fragment in compose

def test_release_database_is_disposable_and_health_checked() -> None:
    compose = read(COMPOSE_PATH)
    assert "pg_isready" in compose
    assert "tmpfs:" in compose
    assert "/var/lib/postgresql/data" in compose
    assert 'restart: "no"' in compose

def test_production_image_runs_as_non_root_with_healthcheck() -> None:
    dockerfile = read(DOCKERFILE_PATH)
    assert "USER novera" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--host" in dockerfile
    assert "0.0.0.0" in dockerfile

def test_release_smoke_checks_hidden_documentation() -> None:
    script = read(RELEASE_SCRIPT_PATH)
    assert 'f"{base_url}/docs"' in script
    assert 'f"{base_url}/redoc"' in script
    assert 'f"{base_url}/openapi.json"' in script
    assert "expected_status=404" in script
    assert "CONTAINER RELEASE SMOKE TEST PASSED." in script
