"""
core.py — Napoleon Mastermind business logic.
No Flask/HTTP dependencies. Returns plain dicts/lists.
"""

import json
import os
import signal
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TOML_CONFIG = BASE_DIR / "config" / "mastermind_config.toml"
PID_FILE = BASE_DIR / "supervisor_loop.pid"
RUN_FILE = BASE_DIR / "supervisor_loop.run"
MEMBERS_AI = BASE_DIR / "members_ai"
PROMPT_DIR = BASE_DIR / "PROMPT"


# ── Config ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load config from TOML (preferred) or legacy .md fallback. Returns flat dict."""
    defaults = {
        "editor_host": "0.0.0.0",
        "editor_port": 7700,
        "editor_refresh_ms": 2000,
        "response_sentences": "4-5",
        "sleep_seconds": 10,
        "backend": "proxy",
    }

    if not TOML_CONFIG.exists():
        return defaults

    with open(TOML_CONFIG, "rb") as f:
        raw = tomllib.load(f)
    cfg = {**defaults}
    cfg.update(raw.get("general", {}))
    cfg["proxy_url"] = raw.get("proxy", {}).get("url", "")
    cfg["proxy_api_key"] = raw.get("proxy", {}).get("api_key", "")
    for k, v in raw.get("editor", {}).items():
        cfg[f"editor_{k}"] = v
    cfg["_models"] = raw.get("models", {})
    cfg["_raw"] = raw
    return cfg


def get_config() -> dict:
    """Structured config for API/UI consumption."""
    if not TOML_CONFIG.exists():
        return {"general": {}, "proxy": {}, "editor": {}, "models": {}}
    with open(TOML_CONFIG, "rb") as f:
        raw = tomllib.load(f)
    return {
        "general": raw.get("general", {}),
        "proxy": raw.get("proxy", {}),
        "editor": raw.get("editor", {}),
        "models": raw.get("models", {}),
        "characters": list_members(),
        "prompt_styles": list_prompts(),
    }


def save_config(data: dict) -> bool:
    """Write config dict to TOML."""
    toml_dict = {
        "general": data.get("general", {}),
        "proxy": data.get("proxy", {}),
        "editor": data.get("editor", {}),
        "models": data.get("models", {}),
    }
    write_toml(toml_dict, TOML_CONFIG)
    return True


def write_toml(data: dict, path: Path):
    """Write a simple 2-level dict as TOML."""
    lines = []
    for section, kvs in data.items():
        if not isinstance(kvs, dict):
            continue
        lines.append(f"[{section}]")
        for k, v in kvs.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            else:
                escaped = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
                lines.append(f'{k} = "{escaped}"')
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


# ── Members ─────────────────────────────────────────────────────────────────

def list_members() -> list[str]:
    if not MEMBERS_AI.exists():
        return []
    return sorted(p.stem for p in MEMBERS_AI.glob("*.md"))


def get_member(name: str) -> dict:
    path = (MEMBERS_AI / f"{name}.md").resolve()
    if not path.is_relative_to(MEMBERS_AI) or not path.exists():
        return {"error": "not found"}
    return {"name": name, "content": path.read_text()}


def save_member(name: str, content: str) -> dict:
    path = (MEMBERS_AI / f"{name}.md").resolve()
    if not path.is_relative_to(MEMBERS_AI):
        return {"error": "forbidden"}
    MEMBERS_AI.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return {"ok": True}


# ── Prompts ─────────────────────────────────────────────────────────────────

def list_prompts() -> list[str]:
    if not PROMPT_DIR.exists():
        return []
    return sorted(p.stem for p in PROMPT_DIR.glob("*.md"))


def get_prompt(name: str) -> dict:
    path = (PROMPT_DIR / f"{name}.md").resolve()
    if not path.is_relative_to(PROMPT_DIR) or not path.exists():
        return {"error": "not found"}
    return {"name": name, "content": path.read_text()}


def save_prompt(name: str, content: str) -> dict:
    path = (PROMPT_DIR / f"{name}.md").resolve()
    if not path.is_relative_to(PROMPT_DIR):
        return {"error": "forbidden"}
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return {"ok": True}


# ── Model Discovery ─────────────────────────────────────────────────────────

def discover_models() -> dict:
    """Query proxy /v1/models endpoint for available models."""
    cfg = get_config()
    proxy = cfg.get("proxy", {})
    api_base = proxy.get("url", os.environ.get("OPENAI_API_BASE", "")).strip().rstrip("/")
    if not api_base:
        return {"models": [], "error": "No proxy URL configured"}
    api_key = proxy.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        req = urllib.request.Request(f"{api_base}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return {"models": sorted(m["id"] for m in body.get("data", []))}
    except Exception as e:
        return {"models": [], "error": str(e)}


# ── Health / Connection Check ────────────────────────────────────────────────

def check_connections() -> dict:
    """Check proxy reachability and SDK availability."""
    result = {"proxy": None, "sdk": None}

    cfg = get_config()
    proxy = cfg.get("proxy", {})
    api_base = proxy.get("url", "").strip().rstrip("/")
    if api_base:
        api_key = proxy.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            req = urllib.request.Request(f"{api_base}/models", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            result["proxy"] = {"ok": True, "models": len(body.get("data", [])), "url": api_base}
        except Exception as e:
            result["proxy"] = {"ok": False, "error": str(e), "url": api_base}
    else:
        result["proxy"] = {"ok": False, "error": "No proxy URL configured"}

    try:
        import litellm  # noqa: F401
        result["sdk"] = {"ok": True, "version": getattr(litellm, "__version__", "unknown")}
    except ImportError:
        result["sdk"] = {"ok": False, "error": "litellm not installed"}

    return result


# ── Loop Management ──────────────────────────────────────────────────────────

def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (TypeError, ValueError):
        return None


def _loop_pids() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", str(BASE_DIR / "supervisor_loop.py")],
        capture_output=True, text=True, check=False,
    )
    return [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]


def loop_status() -> dict:
    pids = _loop_pids()
    pid = pids[0] if pids else _read_pid()
    running = bool(pids)
    if not running and PID_FILE.exists():
        PID_FILE.unlink(missing_ok=True)
        pid = None
    return {"running": running, "pid": pid, "pids": pids, "enabled": RUN_FILE.exists()}


def loop_start() -> dict:
    RUN_FILE.write_text("run\n")
    status = loop_status()
    if status["running"]:
        return status
    proc = subprocess.Popen(
        [sys.executable, "-u", str(BASE_DIR / "functions" / "supervisor_loop.py")],
        cwd=BASE_DIR,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    return {"running": True, "pid": proc.pid, "pids": [proc.pid], "enabled": True}


def loop_stop() -> dict:
    RUN_FILE.unlink(missing_ok=True)
    # Send SIGTERM to all running loop processes for immediate shutdown
    for pid in _loop_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    status = loop_status()
    PID_FILE.unlink(missing_ok=True)
    return {"running": status["running"], "pid": status["pid"], "pids": status.get("pids", []), "enabled": False}
