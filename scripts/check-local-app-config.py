#!/usr/bin/env python3
"""Check that the local browser and Kubernetes settings describe one app."""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"Missing {path}; see frontend/.env.example and README.md")
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def required(values: dict[str, str], key: str, path: Path) -> str:
    value = values.get(key, "")
    if not value or "<" in value or ">" in value:
        raise ValueError(f"Set {key} in {path}")
    return value


def main() -> None:
    backend_path = Path(os.environ.get("ENV_FILE", ".env.kubernetes"))
    frontend_path = Path("frontend/.env.local")
    backend = read_env(backend_path)
    frontend = read_env(frontend_path)
    port = os.environ.get("LOCAL_PORT") or required(backend, "APP_PORT", backend_path)
    ui_port = os.environ.get("FRONTEND_PORT", "5173")
    api_url = required(frontend, "VITE_API_BASE_URL", frontend_path)
    if api_url.rstrip("/") != f"http://localhost:{port}":
        raise ValueError(f"VITE_API_BASE_URL must be http://localhost:{port}")
    for backend_key, frontend_key in (
        ("COGNITO_ISSUER", "VITE_COGNITO_ISSUER"),
        ("COGNITO_CLIENT_ID", "VITE_COGNITO_CLIENT_ID"),
    ):
        if required(backend, backend_key, backend_path) != required(
            frontend, frontend_key, frontend_path
        ):
            raise ValueError(f"{backend_key} and {frontend_key} must match")
    domain = required(frontend, "VITE_COGNITO_DOMAIN", frontend_path)
    if urlsplit(domain).scheme != "https":
        raise ValueError("VITE_COGNITO_DOMAIN must be an HTTPS URL")
    origin = f"http://localhost:{ui_port}"
    callback = required(frontend, "VITE_COGNITO_REDIRECT_URI", frontend_path)
    logout = required(frontend, "VITE_COGNITO_LOGOUT_URI", frontend_path)
    if callback != f"{origin}/auth/callback" or logout != f"{origin}/":
        raise ValueError(f"Set the Cognito callback to {origin}/auth/callback and sign-out to {origin}/")
    cors = required(backend, "CORS_ORIGINS", backend_path)
    if origin not in (item.strip() for item in cors.split(",")):
        raise ValueError(f"Add {origin} to CORS_ORIGINS in {backend_path}")
    print(f"Local configuration matches: UI {origin}, API {api_url}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(1) from None
