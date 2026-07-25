"""Build and exercise the production container with disposable PostgreSQL."""
from __future__ import annotations
import json, os, shutil, socket, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "compose.release.yml"

def run(arguments: list[str], *, environment: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"\n$ {' '.join(arguments)}", flush=True)
    result = subprocess.run(arguments, cwd=ROOT, env=environment, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(arguments)}")
    return result

def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])

def request_json(url: str, *, expected_status: int) -> dict[str, object] | None:
    response = None
    try:
        response = urllib.request.urlopen(url, timeout=5)
        status = response.status
        body = response.read()
        content_type = response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()
        content_type = error.headers.get_content_type()
    finally:
        if response is not None:
            response.close()
    if status != expected_status:
        raise RuntimeError(f"{url} returned {status}; expected {expected_status}. Body: {body.decode('utf-8', errors='replace')}")
    if not body:
        return None
    if content_type == "application/json":
        return json.loads(body)
    return None

def wait_for_api(base_url: str, *, timeout_seconds: int = 90) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = request_json(f"{base_url}/", expected_status=200)
            if payload is None:
                raise RuntimeError("API root returned no JSON payload.")
            return payload
        except (OSError, RuntimeError, urllib.error.URLError) as error:
            last_error = error
            time.sleep(2)
    raise RuntimeError("API did not become healthy before timeout.") from last_error

def main() -> None:
    if not COMPOSE_FILE.exists():
        raise RuntimeError(f"Compose file not found: {COMPOSE_FILE}")
    docker = (shutil.which("docker.exe") or shutil.which("docker"))
    if docker is None:
        raise RuntimeError("Docker is not installed or is not available on PATH.")
    environment = os.environ.copy()
    environment["NOVERA_RELEASE_PORT"] = str(reserve_port())
    compose = [docker, "compose", "--file", str(COMPOSE_FILE)]
    base_url = "http://127.0.0.1:" + environment["NOVERA_RELEASE_PORT"]
    try:
        run([*compose, "version"], environment=environment)
        run([*compose, "config", "--quiet"], environment=environment)
        run([*compose, "build", "--pull"], environment=environment)
        run([*compose, "up", "--detach", "db"], environment=environment)
        run([*compose, "run", "--rm", "migrate"], environment=environment)
        run([*compose, "up", "--detach", "api"], environment=environment)
        payload = wait_for_api(base_url)
        expected_root = {"application": "Novera", "version": "1.0.0", "environment": "production", "status": "running"}
        if payload != expected_root:
            raise RuntimeError(f"Unexpected production root payload: {payload!r}")
        request_json(f"{base_url}/docs", expected_status=404)
        request_json(f"{base_url}/redoc", expected_status=404)
        request_json(f"{base_url}/openapi.json", expected_status=404)
        run([*compose, "ps"], environment=environment)
        print("\nCONTAINER RELEASE SMOKE TEST PASSED.", flush=True)
    finally:
        run([*compose, "down", "--volumes", "--remove-orphans"], environment=environment, check=False)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nRelease smoke test interrupted.", file=sys.stderr)
        raise SystemExit(130)
