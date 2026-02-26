#!/usr/bin/env python3
"""
Setup script for Napoleon Hill's AI Mastermind.
Creates a venv, installs dependencies, and generates sgpt_config.yaml.
Works on macOS, Linux, and Windows.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

BASE_DIR    = Path(__file__).parent
VENV_DIR    = BASE_DIR / "venv"
CONFIG_FILE = BASE_DIR / "sgpt_config.yaml"

PLATFORM = platform.system()  # 'Darwin', 'Linux', 'Windows'

def banner(msg: str):
    print(f"\n{'─'*60}")
    print(f"  {msg}")
    print(f"{'─'*60}")


def get_python_bin() -> str:
    """Find python3 or python executable."""
    for candidate in ["python3", "python"]:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return candidate
        except FileNotFoundError:
            continue
    print("[ERROR] Python not found. Please install Python 3.10+.")
    sys.exit(1)


def create_venv(python_bin: str):
    banner("Creating virtual environment...")
    if VENV_DIR.exists():
        print(f"  venv already exists at {VENV_DIR} — skipping creation.")
        return
    subprocess.run([python_bin, "-m", "venv", str(VENV_DIR)], check=True)
    print(f"  ✅ venv created at {VENV_DIR}")


def get_venv_python() -> str:
    if PLATFORM == "Windows":
        p = VENV_DIR / "Scripts" / "python.exe"
    else:
        p = VENV_DIR / "bin" / "python"
    return str(p)


def get_venv_pip() -> str:
    if PLATFORM == "Windows":
        p = VENV_DIR / "Scripts" / "pip.exe"
    else:
        p = VENV_DIR / "bin" / "pip"
    return str(p)


def install_dependencies():
    banner("Installing dependencies...")
    pip = get_venv_pip()
    packages = [
        "litellm",
    ]
    subprocess.run([pip, "install", "--upgrade", "pip"], check=True)
    subprocess.run([pip, "install"] + packages, check=True)
    print("  ✅ Dependencies installed.")


def create_config():
    banner("Setting up sgpt_config.yaml...")
    if CONFIG_FILE.exists():
        print(f"  Config already exists at {CONFIG_FILE} — skipping.")
        return

    config_content = """# Napoleon Hill Mastermind - Configuration
# ─────────────────────────────────────────────
# Set your API key and model below.
# Only the key for your chosen provider is required.
# ─────────────────────────────────────────────

# Anthropic (claude-*)
ANTHROPIC_API_KEY = YOUR_ANTHROPIC_KEY_HERE

# OpenAI (gpt-*)
# OPENAI_API_KEY = YOUR_OPENAI_KEY_HERE

# Google Gemini (gemini/*)
# GEMINI_API_KEY = YOUR_GEMINI_KEY_HERE

# Groq (groq/*)
# GROQ_API_KEY = YOUR_GROQ_KEY_HERE

# Model to use (litellm format). Examples:
#   Anthropic : claude-sonnet-4-6
#   OpenAI    : gpt-4o
#   Gemini    : gemini/gemini-flash-latest
#   Groq      : groq/llama3-70b-8192
DEFAULT_MODEL = claude-sonnet-4-6
"""
    CONFIG_FILE.write_text(config_content)
    print(f"  ✅ Created {CONFIG_FILE}")


def print_next_steps():
    banner("✅ Setup complete! Next steps:")

    if PLATFORM == "Windows":
        activate = r"venv\Scripts\activate"
        run_cmd  = r"python supervisor_loop.py"
    else:
        activate = "source venv/bin/activate"
        run_cmd  = "python supervisor_loop.py"

    print(f"""
  1. Open sgpt_config.yaml and fill in:
       → Your API key for your chosen provider
       → DEFAULT_MODEL (e.g. claude-sonnet-4-6 or gemini/gemini-flash-latest)

  2. Add your persona to members/
       → Copy members/member_template.md and edit it

  3. Create a session in sessions/
       → Copy sessions/session_template.md and edit it

  4. Activate the venv and start the loop:
       {activate}
       {run_cmd}

  The loop rotates through AI members and responds automatically.
  When it's a human's turn, it waits for you to write into the session file.
""")


def main():
    banner("Napoleon Hill's AI Mastermind — Setup")
    print(f"  Platform : {PLATFORM}")
    print(f"  Base dir : {BASE_DIR}")

    python_bin = get_python_bin()
    print(f"  Python   : {python_bin}")

    create_venv(python_bin)
    install_dependencies()
    create_config()
    print_next_steps()


if __name__ == "__main__":
    main()
