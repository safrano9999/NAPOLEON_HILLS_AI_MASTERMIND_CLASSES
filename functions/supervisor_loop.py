#!/usr/bin/env python3
"""
Napoleon Hill's AI Mastermind - Supervisor Loop
Rotates through AI members, calls litellm for each matching speaker in sessions.
Reads configuration from .env (API keys) and mastermind_config.md (settings).
"""

from python_header import get  # noqa: F401 — loads .env

import os
import sys
import time
import subprocess
import json
import re
import tomllib
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
# Project root is one level above functions/
BASE_DIR      = Path(__file__).resolve().parent.parent
MEMBERS_AI    = BASE_DIR / "members_ai"
MEMBERS_HUMAN = BASE_DIR / "members"
MEMBERS_AGENT = BASE_DIR / "members_agents"
SESSIONS_DIR  = BASE_DIR / "sessions"
RULES_FILE    = BASE_DIR / "rules.md"
CONFIG_FILE   = BASE_DIR / "mastermind_config.md"  # legacy fallback
TOML_CONFIG   = BASE_DIR / "config" / "mastermind_config.toml"
RUN_FILE      = BASE_DIR / "supervisor_loop.run"
PROMPT_DIR    = BASE_DIR / "PROMPT"


# ── Config loading ───────────────────────────────────────────────────────────

def load_config() -> dict:
    """
    Load config from mastermind_config.toml (preferred) or .md (legacy fallback).
    Returns flat dict with defaults for missing values.
    """
    defaults = {
        "sleep_seconds": 0.5,
        "response_sentences": "4-5",
        "prompt_style": "default",
        "backend": "proxy",
    }

    if TOML_CONFIG.exists():
        with open(TOML_CONFIG, "rb") as f:
            raw = tomllib.load(f)
        cfg = {**defaults}
        cfg.update(raw.get("general", {}))
        cfg["proxy_url"] = raw.get("proxy", {}).get("url", "")
        cfg["proxy_api_key"] = raw.get("proxy", {}).get("api_key", "")
        for k, v in raw.get("editor", {}).items():
            cfg[f"editor_{k}"] = v
        cfg["_models"] = raw.get("models", {})
        return cfg

    # Legacy fallback: parse mastermind_config.md
    allowed_keys = set(defaults) | {"default_model"}
    if not CONFIG_FILE.exists():
        print("[INFO] No config file found, using defaults.")
        return defaults

    cfg = {}
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-") or line.startswith("*"):
            continue
        if line == "---":
            continue
        if ":" in line and not line.startswith("http"):
            k, _, v = line.partition(":")
            k = k.strip().lower().replace(" ", "_")
            v = v.strip().strip('"').strip("'")
            if k in allowed_keys:
                if v.replace(".", "", 1).isdigit():
                    v = float(v) if "." in v else int(v)
                elif v.lower() in ("true", "false"):
                    v = v.lower() == "true"
                cfg[k] = v

    return {**defaults, **cfg}


def reload_config():
    """Reload config from file (called each cycle for live updates)."""
    global CFG, SLEEP_SECONDS
    CFG = load_config()
    SLEEP_SECONDS = CFG.get("sleep_seconds", 10)


def loop_enabled() -> bool:
    return RUN_FILE.exists()


def wait_or_stop(seconds: float) -> bool:
    deadline = time.time() + max(float(seconds), 0.0)
    while time.time() < deadline:
        if not loop_enabled():
            return False
        time.sleep(min(0.25, deadline - time.time()))
    return loop_enabled()


# Initial load
CFG = load_config()
SLEEP_SECONDS = CFG.get("sleep_seconds", 10)


# ── Environment loading ──────────────────────────────────────────────────────

def load_env() -> dict:
    """Return current environment (already loaded by python_header)."""
    return dict(os.environ)


# ── Member helpers ───────────────────────────────────────────────────────────

def get_ai_members() -> list[str]:
    """Return sorted list of AI member names (filenames without .md)."""
    if not MEMBERS_AI.exists():
        return []
    return sorted(p.stem for p in MEMBERS_AI.glob("*.md"))


def get_human_members() -> list[str]:
    if not MEMBERS_HUMAN.exists():
        return []
    return sorted(p.stem for p in MEMBERS_HUMAN.glob("*.md"))


def member_exists(name: str) -> bool:
    """Check if a member MD file exists in any members folder."""
    for folder in [MEMBERS_AI, MEMBERS_HUMAN, MEMBERS_AGENT]:
        if (folder / f"{name}.md").exists():
            return True
    return False


def is_human(name: str) -> bool:
    return (MEMBERS_HUMAN / f"{name}.md").exists()


def read_member_md(name: str) -> str:
    for folder in [MEMBERS_AI, MEMBERS_HUMAN, MEMBERS_AGENT]:
        p = folder / f"{name}.md"
        if p.exists():
            return p.read_text()
    return ""


def get_member_model(name: str) -> str | None:
    """
    Resolve model for a member with 3-tier priority:
    1. model: line in .md file (highest)
    2. [models] table in TOML config
    3. None → caller falls back to default_model
    """
    content = read_member_md(name)
    if content:
        for line in content.splitlines()[:3]:
            line = line.strip()
            if line.lower().startswith("model:"):
                return line.split(":", 1)[1].strip()

    toml_models = CFG.get("_models", {})
    if name in toml_models:
        return toml_models[name]

    return None


# ── Session parsing ──────────────────────────────────────────────────────────

def parse_session(path: Path) -> dict | None:
    """
    Parse a session MD file.
    Returns dict with keys: title, members, thesis, speakers, last_speaker, content
    or None on hard error.
    """
    text = path.read_text().replace('\r', '')
    lines = text.splitlines()

    if len(lines) < 2:
        print(f"[ERROR] {path.name}: File too short.")
        return None

    title = lines[0].lstrip("# ").strip()

    # parse members: line
    members_line = ""
    for line in lines[1:4]:
        if line.lower().startswith("members:"):
            members_line = line
            break
    if not members_line:
        print(f"[ERROR] {path.name}: No 'members:' line found.")
        return None

    raw_members = members_line.split(":", 1)[1]
    members = [m.strip() for m in raw_members.split(",") if m.strip()]

    # parse optional thesis:
    thesis = ""
    for line in lines:
        if line.lower().startswith("thesis:"):
            thesis = line.split(":", 1)[1].strip()
            break

    # check at least one speaker: exists
    speaker_pattern = re.compile(r"^speaker:\s*(.+)$", re.IGNORECASE)
    speakers_found = [m.group(1).strip() for l in lines if (m := speaker_pattern.match(l))]

    if not speakers_found:
        print(f"[ERROR] {path.name}: No 'speaker:' found. Please initiate the conversation.")
        return None

    last_speaker = speakers_found[-1]

    return {
        "path": path,
        "title": title,
        "members": members,
        "thesis": thesis,
        "speakers_found": speakers_found,
        "last_speaker": last_speaker,
        "text": text,
        "lines": lines,
    }


def validate_members(session: dict) -> bool:
    """Check all session members exist as MD files. Abort if not."""
    all_ok = True
    for name in session["members"]:
        if not member_exists(name):
            print(f"[ERROR] {session['path'].name}: Member '{name}' has no MD file in members_ai/, members/, or members_agents/.")
            all_ok = False
    return all_ok


def next_speaker(current: str, members: list[str]) -> str:
    """Return the member after current in the list (wrap-around)."""
    if current not in members:
        return members[0]
    idx = members.index(current)
    return members[(idx + 1) % len(members)]


def ensure_next_speaker_line(session: dict) -> str:
    """
    Check if the last line of the file is 'speaker: NAME'.
    If not, compute next speaker and append it.
    Returns the actual_speaker name.
    """
    path: Path = session["path"]
    lines = session["lines"]

    # find last non-empty line
    last_line = ""
    for line in reversed(lines):
        if line.strip():
            last_line = line.strip()
            break

    speaker_pattern = re.compile(r"^speaker:\s*(.+)$", re.IGNORECASE)
    m = speaker_pattern.match(last_line)

    if m:
        return m.group(1).strip()

    # need to append next speaker line
    nxt = next_speaker(session["last_speaker"], session["members"])
    with open(path, "a") as f:
        f.write(f"\nspeaker: {nxt}\n")
    print(f"  → Appended 'speaker: {nxt}' to {path.name}")
    return nxt


# ── LLM call ─────────────────────────────────────────────────────────────────

def is_kilocode_model(model: str) -> bool:
    """Check if model is a Kilocode model (starts with kilocode/)."""
    return model.startswith("kilocode/")


def use_openai_compatible_api() -> bool:
    """Route model calls through an OpenAI-compatible /v1 endpoint when backend=proxy."""
    if CFG.get("backend") == "proxy":
        return bool(openai_api_base())
    return False


def openai_api_base() -> str:
    # TOML proxy.url takes precedence over env var
    toml_url = CFG.get("proxy_url", "").strip().rstrip("/")
    if toml_url:
        return toml_url
    return os.environ.get("OPENAI_API_BASE", "").strip().rstrip("/")


def normalize_openai_model(model: str) -> str:
    """
    Map existing per-persona model strings to model names accepted by an
    OpenAI-compatible endpoint.
    """
    if model.startswith("openai/"):
        return model.split("/", 1)[1]
    return model


def call_openai_compatible(model: str, prompt: str) -> str:
    api_base = openai_api_base()
    api_key = CFG.get("proxy_api_key", "").strip() or os.environ.get("OPENAI_API_KEY", "")
    if not api_base:
        raise RuntimeError("OPENAI_API_BASE is empty")

    payload = {
        "model": normalize_openai_model(model),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        url=f"{api_base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI-compatible API error {exc.code} from {api_base}/chat/completions: {error_body[:400]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach OpenAI-compatible API at {api_base}: {exc}") from exc

    parsed = json.loads(body)
    try:
        return parsed["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenAI-compatible response: {body[:400]}") from exc


def call_llm(session: dict, speaker_name: str) -> str | None:
    """Build prompt, call the configured LLM backend, return parsed response text."""
    # Reload config to get latest settings
    reload_config()

    persona_md   = read_member_md(speaker_name)
    rules_text   = RULES_FILE.read_text() if RULES_FILE.exists() else ""
    session_text = session["text"]

    sentences = CFG.get("response_sentences", "4-5")
    style     = CFG.get("prompt_style", "default")

    # Load prompt template from PROMPT/<style>.md (fallback: default.md)
    template_path = PROMPT_DIR / f"{style}.md"
    if not template_path.exists():
        print(f"  [WARN] Prompt style '{style}' not found, falling back to default.")
        template_path = PROMPT_DIR / "default.md"
    if not template_path.exists():
        raise RuntimeError(f"Missing prompt template: {template_path}")

    template = template_path.read_text()
    prompt = template.format(
        speaker_name=speaker_name,
        persona_md=persona_md,
        rules_text=rules_text,
        session_text=session_text,
        sentences=sentences,
    )

    # Check if persona has a specific model, otherwise use default
    persona_model = get_member_model(speaker_name)
    model = persona_model if persona_model else CFG.get("default_model")

    if not model:
        raise RuntimeError("Missing default_model in mastermind_config.md")

    if persona_model:
        print(f"  [DEBUG] Using persona model: '{model}'")
    else:
        print(f"  [DEBUG] Using default model: '{model}'")

    try:
        if use_openai_compatible_api():
            print(f"  [DEBUG] Using OpenAI-compatible API base: '{openai_api_base()}'")
            raw = call_openai_compatible(model, prompt)
        else:
            import litellm

            # Kilocode-Support: use custom api_base and api_key
            if is_kilocode_model(model):
                model_name = model.replace("kilocode/", "")
                response = litellm.completion(
                    model=f"openai/{model_name}",
                    api_base="https://api.kilo.ai/api/gateway/",
                    api_key=os.environ.get("KILOCODE_API_KEY"),
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                )
            else:
                # Normal litellm flow for other providers
                response = litellm.completion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                )
            raw = response.choices[0].message.content.strip()

        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*",     "", raw)
        raw = re.sub(r"```$",        "", raw).strip()

        parsed = json.loads(raw)
        return parsed.get("response", "").strip()

    except json.JSONDecodeError as e:
        print(f"  [ERROR] Invalid JSON for {speaker_name}: {e}")
        print(f"  Raw: {raw[:200]}")
        return None
    except Exception as e:
        backend = "OpenAI-compatible API" if use_openai_compatible_api() else "litellm"
        print(f"  [ERROR] {backend} call failed for {speaker_name}: {e}")
        return None


def append_response(session: dict, speaker_name: str, response: str):
    """Append the speaker's response and a timestamp to the session file."""
    path: Path = session["path"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a") as f:
        f.write(f"{response}\n")
        f.write(f"\n<!-- {ts} -->\n")
    print(f"  ✅ {speaker_name} responded in {path.name}")


# ── Main loop ────────────────────────────────────────────────────────────────

def run():
    load_env()  # load .env into environment

    if not loop_enabled():
        print("[EXIT] supervisor_loop.run not present. Start via web UI or create the run file.")
        return

    # startup warnings
    ai_members = get_ai_members()
    if not ai_members:
        print("[ERROR] No AI members found in members_ai/. Add at least one .md file.")
        sys.exit(1)

    human_members = get_human_members()
    if not human_members:
        print("[WARNING] No human members found in members/. The session will run passively (AI only).")

    print(f"[INFO] AI members: {ai_members}")
    print(f"[INFO] Human members: {human_members}")
    print(f"[INFO] Config file: {'found' if CONFIG_FILE.exists() else 'not found (using defaults)'}")
    print(f"[INFO] Model: {CFG.get('default_model')}")
    print(f"[INFO] Response sentences: {CFG.get('response_sentences')}")
    print(f"[INFO] Starting mastermind loop. Sleep between cycles: {SLEEP_SECONDS}s\n")

    ai_index = 0  # tracks position in ai_members rotation

    while True:
        if not loop_enabled():
            print("\n[EXIT] Stop requested. Leaving mastermind loop.")
            return

        # Reload config each cycle (allows live editing via web UI)
        reload_config()

        member_actual = ai_members[ai_index]
        print(f"\n{'='*60}")
        print(f"[CYCLE] member_actual: {member_actual}  ({datetime.now().strftime('%H:%M:%S')})")
        print(f"{'='*60}")

        # get all session files sorted alphabetically, skip templates
        session_files = sorted(
            p for p in SESSIONS_DIR.glob("*.md")
            if not p.name.endswith("_template.md")
        )
        if not session_files:
            print("[INFO] No session files found in sessions/. Add a session MD to begin.")

        for session_path in session_files:
            if not loop_enabled():
                print("\n[EXIT] Stop requested. Leaving mastermind loop.")
                return

            print(f"\n[SESSION] {session_path.name}")

            session = parse_session(session_path)
            if session is None:
                # hard error already printed inside parse_session
                continue

            # Check for PAUSE in session
            if "PAUSE" in session["text"]:
                print(f"  ⏸️  PAUSE detected — skipping this session.")
                continue

            # validate all members exist — abort this session on error
            if not validate_members(session):
                print(f"  [SKIP] {session_path.name}: member validation failed.")
                continue

            # ensure last line is speaker: NAME → get actual_speaker
            actual_speaker = ensure_next_speaker_line(session)
            # re-read session after possible append
            session = parse_session(session_path)
            if session is None:
                continue

            print(f"  actual_speaker: {actual_speaker} | member_actual: {member_actual}")

            if actual_speaker != member_actual:
                if is_human(actual_speaker):
                    print(f"  ⏳ Waiting for human '{actual_speaker}' to respond.")
                else:
                    print(f"  → Not my turn (I am {member_actual}, speaker is {actual_speaker}).")
                continue

            # it's our turn!
            backend = "OpenAI-compatible API" if use_openai_compatible_api() else "litellm"
            print(f"  🎙️  Calling {backend} for {member_actual}...")
            response = call_llm(session, member_actual)
            if response:
                append_response(session, member_actual, response)
            else:
                print(f"  [ERROR] No response from {backend} for {member_actual}. Skipping.")

        # advance to next AI member
        ai_index = (ai_index + 1) % len(ai_members)

        # Reload config to get latest sleep_seconds (live editing)
        reload_config()
        print(f"\n[SLEEP] Sleeping {SLEEP_SECONDS}s before next cycle...")
        if not wait_or_stop(SLEEP_SECONDS):
            print("\n[EXIT] Stop requested during sleep. Leaving mastermind loop.")
            return


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[EXIT] Mastermind loop stopped by user.")
