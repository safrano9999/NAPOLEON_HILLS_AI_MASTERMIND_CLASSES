"""
core.py — Napoleon Mastermind business logic.
No Flask/HTTP dependencies. Returns plain dicts/lists.
"""

import os
import signal
import subprocess
import sys
import tomllib
from pathlib import Path

from python_header import (  # noqa: F401 — loads config.conf/.env
    get,
    openai_v1_client,
    openai_v1_first_provider,
    openai_v1_models,
    openai_v1_provider_for_model,
    openai_v1_providers,
)
import storage

BASE_DIR = Path(__file__).resolve().parent.parent
TOML_CONFIG = BASE_DIR / "config" / "mastermind_config.toml"
CONFIG_DOCUMENT = "config/mastermind_config.toml"
PID_FILE = BASE_DIR / "supervisor_loop.pid"
RUN_FILE = BASE_DIR / "supervisor_loop.run"
DEFAULT_LLM_ENV_KEY = "NAPOLEON_OPENAI_V1_DEFAULT_LLM"

storage.import_if_empty()


# ── Config ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load config from TOML and env overrides. Returns flat dict."""
    defaults = {
        "editor_host": "0.0.0.0",
        "editor_port": 11004,
        "editor_refresh_ms": 2000,
        "response_sentences": "4-5",
        "sleep_seconds": 10,
        "backend": "proxy",
    }

    content = storage.read_document(CONFIG_DOCUMENT)
    if content is None:
        return defaults

    raw = tomllib.loads(content)
    cfg = {**defaults}
    cfg.update(raw.get("general", {}))
    for k, v in raw.get("editor", {}).items():
        cfg[f"editor_{k}"] = v
    cfg["_models"] = raw.get("models", {})
    cfg["_raw"] = raw
    default_model = get_default_model()
    if default_model:
        cfg["default_model"] = default_model
    return cfg


def _clean(value: str | None) -> str:
    return (value or "").strip().strip('"').strip("'")


def get_default_model() -> str:
    return _clean(os.environ.get(DEFAULT_LLM_ENV_KEY))


def openai_api_base(model: str = "") -> str:
    provider = openai_v1_provider_for_model(model) if model else openai_v1_first_provider()
    return provider.base_url if provider else ""


def openai_api_key(model: str = "") -> str:
    provider = openai_v1_provider_for_model(model) if model else openai_v1_first_provider()
    return provider.api_key if provider else ""


def openai_client(api_base: str = "", api_key: str = "", timeout: float = 10.0, model: str = ""):
    provider = openai_v1_provider_for_model(model) if model else openai_v1_first_provider()
    return openai_v1_client(provider, timeout=timeout)


def proxy_model_ids(api_base: str, api_key: str = "", timeout: float = 10.0) -> list[str]:
    models: list[str] = []
    for provider in openai_v1_providers():
        try:
            models.extend(openai_v1_models(provider, timeout=timeout))
        except Exception:
            continue
    return sorted(set(models))


def get_config() -> dict:
    """Structured config for API/UI consumption."""
    content = storage.read_document(CONFIG_DOCUMENT)
    if content is None:
        return {"general": {}, "proxy": {}, "editor": {}, "models": {}}
    raw = tomllib.loads(content)
    general = raw.get("general", {})
    if not isinstance(general, dict):
        general = {}
    default_model = get_default_model()
    if default_model:
        general = {**general, "default_model": default_model}

    return {
        "general": general,
        "proxy": {"url": openai_api_base(), "api_key": ""},
        "editor": raw.get("editor", {}),
        "models": raw.get("models", {}),
        "characters": list_members(),
        "prompt_styles": list_prompts(),
    }


def save_config(data: dict) -> bool:
    """Write config dict to TOML."""
    toml_dict = {
        "general": data.get("general", {}),
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
    storage.write_document(path.relative_to(BASE_DIR).as_posix(), "\n".join(lines) + "\n")


# ── Document Files ───────────────────────────────────────────────────────────

def list_folder(folder: str) -> list[str]:
    return storage.list_document_names(folder)


def list_root_markdown() -> list[str]:
    return storage.list_root_markdown()


def file_exists(path: str) -> bool:
    try:
        return storage.document_exists(path)
    except ValueError:
        return False


def get_file(path: str) -> dict:
    try:
        content = storage.read_document(path)
    except ValueError:
        return {"error": "forbidden"}
    if content is None:
        return {"error": "not found"}
    return {"content": content}


def save_file(path: str, content: str) -> dict:
    try:
        storage.write_document(path, content)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"ok": True}


def import_presets(force: bool = False) -> dict:
    return storage.import_presets(force=force)


def export_presets() -> dict:
    return storage.export_to_files()


# ── Members ─────────────────────────────────────────────────────────────────

def list_members() -> list[str]:
    return storage.list_document_stems("members_ai")


def get_member(name: str) -> dict:
    content = storage.read_document(f"members_ai/{name}.md")
    if content is None:
        return {"error": "not found"}
    return {"name": name, "content": content}


def save_member(name: str, content: str) -> dict:
    try:
        storage.write_document(f"members_ai/{name}.md", content)
    except ValueError:
        return {"error": "forbidden"}
    return {"ok": True}


# ── Prompts ─────────────────────────────────────────────────────────────────

def list_prompts() -> list[str]:
    return storage.list_document_stems("PROMPT")


def get_prompt(name: str) -> dict:
    content = storage.read_document(f"PROMPT/{name}.md")
    if content is None:
        return {"error": "not found"}
    return {"name": name, "content": content}


def save_prompt(name: str, content: str) -> dict:
    try:
        storage.write_document(f"PROMPT/{name}.md", content)
    except ValueError:
        return {"error": "forbidden"}
    return {"ok": True}


# ── Model Discovery ─────────────────────────────────────────────────────────

def discover_models() -> dict:
    """Query proxy /v1/models endpoint for available models."""
    api_base = openai_api_base()
    if not api_base:
        return {"models": [], "error": "No proxy URL configured"}
    try:
        return {"models": proxy_model_ids(api_base, openai_api_key(), timeout=10.0)}
    except Exception as e:
        return {"models": [], "error": str(e)}


# ── Health / Connection Check ────────────────────────────────────────────────

def check_connections() -> dict:
    """Check proxy reachability."""
    result = {"proxy": None}

    api_base = openai_api_base()
    if api_base:
        try:
            models = proxy_model_ids(api_base, openai_api_key(), timeout=5.0)
            result["proxy"] = {"ok": True, "models": len(models), "url": api_base}
        except Exception as e:
            result["proxy"] = {"ok": False, "error": str(e), "url": api_base}
    else:
        result["proxy"] = {"ok": False, "error": "No proxy URL configured"}

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
