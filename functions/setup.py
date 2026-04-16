#!/usr/bin/env python3
"""
Minimal project installer.

Creates a local venv and installs only the packages needed for the configured
runtime mode:
- always: Flask for webui.py
- optional: litellm when no OPENAI_API_BASE is configured
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE_FILE = BASE_DIR / "env_example.txt"


def load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def merged_env() -> dict[str, str]:
    env = dict(os.environ)
    file_env = load_env_file(ENV_FILE)
    if not file_env and ENV_EXAMPLE_FILE.exists():
        file_env = load_env_file(ENV_EXAMPLE_FILE)
    env.update(file_env)
    return env


def ensure_venv() -> Path:
    if not VENV_DIR.exists():
        print(f"[setup] Creating venv at {VENV_DIR}")
        venv.create(VENV_DIR, with_pip=True)
    return VENV_DIR / "bin" / "python"


def run(python_bin: Path, *args: str) -> None:
    cmd = [str(python_bin), *args]
    print(f"[setup] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def required_packages(env: dict[str, str]) -> list[str]:
    packages = ["flask"]
    if not env.get("OPENAI_API_BASE", "").strip():
        packages.append("litellm")
    return packages


def main() -> int:
    env = merged_env()
    python_bin = ensure_venv()

    run(python_bin, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")

    packages = required_packages(env)
    run(python_bin, "-m", "pip", "install", "--upgrade", *packages)

    print("[setup] Installed packages:")
    for package in packages:
        print(f"[setup]   - {package}")

    if env.get("OPENAI_API_BASE", "").strip():
        print("[setup] OPENAI_API_BASE detected; skipped litellm installation.")
    else:
        print("[setup] OPENAI_API_BASE not set; installed litellm for local provider mode.")

    print(f"[setup] Done. Use {python_bin} or run project scripts directly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
