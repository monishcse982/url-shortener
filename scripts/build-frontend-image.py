#!/usr/bin/env python3
"""Build the static UI image using public Vite configuration."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    env_file = Path("frontend/.env.local")
    if not env_file.is_file():
        raise SystemExit("Missing frontend/.env.local; see frontend/.env.example")
    values = dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    keys = (
        "VITE_API_BASE_URL",
        "VITE_COGNITO_ISSUER",
        "VITE_COGNITO_CLIENT_ID",
        "VITE_COGNITO_DOMAIN",
        "VITE_COGNITO_REDIRECT_URI",
        "VITE_COGNITO_LOGOUT_URI",
    )
    command = ["docker", "build", "--tag", sys.argv[1]]
    for key in keys:
        value = values.get(key, "").strip()
        if not value or "<" in value or ">" in value:
            raise SystemExit(f"Set {key} in {env_file}")
        command.extend(("--build-arg", f"{key}={value}"))
    subprocess.run([*command, "frontend"], check=True)


if __name__ == "__main__":
    main()
