"""Read simple key/value files used for local deployment settings."""

from pathlib import Path


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
