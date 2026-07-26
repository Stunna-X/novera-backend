"""
Regression tests for CI and container release assets.
"""

from __future__ import annotations

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_ROOT.parent

WORKFLOW_PATH = (
    REPOSITORY_ROOT
    / ".github"
    / "workflows"
    / "backend-ci.yml"
)
COMPOSE_PATH = BACKEND_ROOT / "compose.release.yml"
DOCKERFILE_PATH = BACKEND_ROOT / "Dockerfile"
RELEASE_SCRIPT_PATH = (
    BACKEND_ROOT
    / "scripts"
    / "release_smoke.py"
)


def read(path: Path) -> str:
    """
    Read one required release asset.
    """

    assert path.is_file(), f"Missing release asset: {path}"

    return path.read_text(encoding="utf-8")


def test_ci_runs_database_migrations_and_complete_suite() -> None:
    """
    CI must exercise migrations, schema checks, tests, and image builds.
    """

    workflow = read(WORKFLOW_PATH)

    required_fragments = {
        "postgres:17-alpine",
        "alembic upgrade head",
        "python -m app.scripts.seed_access_control",
        "alembic check",
        "python -m pytest -q",
        "docker build --tag novera-backend:ci ./backend",
    }

    for fragment in required_fragments:
        assert fragment in workflow


def test_ci_uses_safe_test_database_and_expected_cors_origin() -> None:
    """
    CI integration tests must use an explicitly named test database.
    """

    workflow = read(WORKFLOW_PATH)

    assert "POSTGRES_DB: novera_test_ci" in workflow
    assert "pg_isready -U postgres -d novera_test_ci" in workflow

    assert (
        "DATABASE_URL: "
        "postgresql+psycopg2://postgres:postgres"
        "@127.0.0.1:5432/novera_test_ci"
        in workflow
    )

    assert (
        "TEST_DATABASE_URL: "
        "postgresql+psycopg2://postgres:postgres"
        "@127.0.0.1:5432/novera_test_ci"
        in workflow
    )

    assert "https://frontend.api-smoke.test" in workflow


def test_ci_has_restricted_permissions_and_concurrency() -> None:
    """
    CI permissions and duplicate-run cancellation must stay restricted.
    """

    workflow = read(WORKFLOW_PATH)

    assert "permissions:\n  contents: read" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "pull_request:" in workflow
    assert "branches:\n      - main" in workflow


def test_release_compose_uses_production_safeguards() -> None:
    """
    Release Compose must use production-safe application settings.
    """

    compose = read(COMPOSE_PATH)

    required_fragments = {
        "APP_ENV: production",
        'DEBUG: "false"',
        'ENABLE_API_DOCS: "false"',
        'LOG_JSON: "true"',
        "EMAIL_PROVIDER: manual",
        "condition: service_healthy",
        "alembic",
        "upgrade",
        "head",
    }

    for fragment in required_fragments:
        assert fragment in compose


def test_release_database_is_disposable_and_health_checked() -> None:
    """
    Release verification must not preserve its PostgreSQL database.
    """

    compose = read(COMPOSE_PATH)

    assert "pg_isready" in compose
    assert "tmpfs:" in compose
    assert "/var/lib/postgresql/data" in compose
    assert 'restart: "no"' in compose


def test_production_image_runs_as_non_root_with_healthcheck() -> None:
    """
    The production image must run safely as the Novera user.
    """

    dockerfile = read(DOCKERFILE_PATH)

    assert "USER novera" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--host" in dockerfile
    assert "0.0.0.0" in dockerfile


def test_release_smoke_checks_hidden_documentation() -> None:
    """
    Production smoke verification must confirm API docs are hidden.
    """

    script = read(RELEASE_SCRIPT_PATH)

    assert 'f"{base_url}/docs"' in script
    assert 'f"{base_url}/redoc"' in script
    assert 'f"{base_url}/openapi.json"' in script
    assert "expected_status=404" in script
    assert "CONTAINER RELEASE SMOKE TEST PASSED." in script
