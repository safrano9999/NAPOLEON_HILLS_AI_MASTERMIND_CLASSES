#!/usr/bin/env python3
"""
Napoleon Hill's AI Mastermind - Supervisor Loop
Rotates through AI members, spawns sgpt for each matching speaker in sessions.
"""

import os
import sys
import time
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime

# ── add venv site-packages so litellm is available ───────────────────────────
_venv_site = Path(__file__).parent / "venv" / "lib"
if _venv_site.exists():
    for _p in _venv_site.glob("python*/site-packages"):
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
MEMBERS_AI    = BASE_DIR / "members_ai"
MEMBERS_HUMAN = BASE_DIR / "members"
MEMBERS_AGENT = BASE_DIR / "members_agents"
SESSIONS_DIR  = BASE_DIR / "sessions"
RULES_FILE    = BASE_DIR / "rules.md"
CONFIG_FILE   = BASE_DIR / "sgpt_config.yaml"

SLEEP_SECONDS = 10   # sleep between full rotations

# ── Config helpers ───────────────────────────────────────────────────────────

def load_config() -> dict:
    """Read DEFAULT_MODEL from sgpt_config.yaml. That's all we need."""
    cfg = {}
    if not CONFIG_FILE.exists():
        print(f"[ERROR] sgpt_config.yaml not found. Run setup.py first.")
        sys.exit(1)
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            cfg[k.strip()] = v.strip()
    return cfg


def build_sgpt_cmd(cfg: dict) -> list:
    """Build the sgpt command list from config. Always use system sgpt."""
    model = cfg.get("DEFAULT_MODEL", "gemini/gemini-flash-latest")
    return ["sgpt", "--model", model, "--no-md", "--no-cache"]


def build_env(cfg: dict) -> dict:
    """Build environment for sgpt using only the local sgpt_config.yaml."""
    env = os.environ.copy()
    for k, v in cfg.items():
        env[k] = v
    env["SGPT_CONFIG"] = str(CONFIG_FILE)
    return env


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


# ── sgpt call ────────────────────────────────────────────────────────────────

def call_sgpt(session: dict, speaker_name: str, cfg: dict) -> str | None:
    """Build prompt, call sgpt via subprocess, return parsed response text."""
    persona_md   = read_member_md(speaker_name)
    rules_text   = RULES_FILE.read_text() if RULES_FILE.exists() else ""
    session_text = session["text"]

    prompt = f"""You are {speaker_name} in a Napoleon Hill Mastermind session.

=== YOUR PERSONA ===
{persona_md}

=== RULES ===
{rules_text}

=== SESSION (full conversation so far) ===
{session_text}

=== YOUR TASK ===
It is now your turn to speak as {speaker_name}.
Read the full conversation above and respond in character.

Return ONLY strict JSON with exactly these keys:
{{
  "speaker": "{speaker_name}",
  "response": "Your 4-5 sentence response here."
}}

No preamble. No markdown. No explanation. Only the JSON object.
"""

    sgpt_cmd = build_sgpt_cmd(cfg)
    env = build_env(cfg)

    # set all keys in env so litellm picks the right one
    for k, v in cfg.items():
        os.environ[k] = v

    import litellm
    model = cfg.get("DEFAULT_MODEL", "gemini/gemini-flash-latest")

    try:
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
        print(f"  [ERROR] litellm call failed for {speaker_name}: {e}")
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
    cfg = load_config()

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
    print(f"[INFO] Starting mastermind loop. Sleep between cycles: {SLEEP_SECONDS}s\n")

    ai_index = 0  # tracks position in ai_members rotation

    while True:
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
            print(f"\n[SESSION] {session_path.name}")

            session = parse_session(session_path)
            if session is None:
                # hard error already printed inside parse_session
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
            print(f"  🎙️  Spawning sgpt for {member_actual}...")
            response = call_sgpt(session, member_actual, cfg)
            if response:
                append_response(session, member_actual, response)
            else:
                print(f"  [ERROR] No response from sgpt for {member_actual}. Skipping.")

        # advance to next AI member
        ai_index = (ai_index + 1) % len(ai_members)

        print(f"\n[SLEEP] Sleeping {SLEEP_SECONDS}s before next cycle...")
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[EXIT] Mastermind loop stopped by user.")
