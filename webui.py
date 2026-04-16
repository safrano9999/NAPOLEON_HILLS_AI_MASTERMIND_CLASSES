#!/usr/bin/env python3
"""
webui.py — Napoleon Hill Mastermind web editor.
Lives in the project root. Shows all .md files across all folders.
Now includes mastermind_config.md for easy configuration editing.
Run: python3 webui.py
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "functions"))

os.environ.setdefault("FLASK_SKIP_DOTENV", "1")

# ── add venv site-packages so flask is available ────────────────────────────
_venv_site = Path(__file__).parent / "venv" / "lib"
if _venv_site.exists():
    for _p in _venv_site.glob("python*/site-packages"):
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))

from python_header import get, get_port  # noqa: F401 — loads .env
from flask import Flask, request, jsonify, render_template_string, send_from_directory

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "mastermind_config.md"
PID_FILE = BASE_DIR / "supervisor_loop.pid"
RUN_FILE = BASE_DIR / "supervisor_loop.run"


def read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (TypeError, ValueError):
        return None


def loop_pids() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", str(BASE_DIR / "supervisor_loop.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def get_loop_status() -> dict:
    pids = loop_pids()
    pid = pids[0] if pids else read_pid()
    running = bool(pids)
    if not running and PID_FILE.exists():
        PID_FILE.unlink(missing_ok=True)
        pid = None
    return {"running": running, "pid": pid, "pids": pids, "enabled": RUN_FILE.exists()}


def start_loop() -> dict:
    RUN_FILE.write_text("run\n")
    status = get_loop_status()
    if status["running"]:
        return status

    proc = subprocess.Popen(
        [sys.executable, "-u", str(BASE_DIR / "supervisor_loop.py")],
        cwd=BASE_DIR,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    return {"running": True, "pid": proc.pid, "pids": [proc.pid], "enabled": True}


def stop_loop() -> dict:
    RUN_FILE.unlink(missing_ok=True)
    status = get_loop_status()
    PID_FILE.unlink(missing_ok=True)
    return {"running": status["running"], "pid": status["pid"], "pids": status.get("pids", []), "enabled": False}


def load_config() -> dict:
    """
    Load mastermind_config.md - parses key: value lines.
    Returns dict with defaults for missing values.
    """
    defaults = {
        "editor_host": "0.0.0.0",
        "editor_port": 7700,
        "editor_refresh_ms": 2000,
        "response_sentences": "4-5",
        "sleep_seconds": 10,
    }
    allowed_keys = set(defaults) | {"default_model"}

    if not CONFIG_FILE.exists():
        return defaults

    cfg = {}
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        # Skip empty lines, comments, headers, and markdown formatting
        if not line or line.startswith("#") or line.startswith("-") or line.startswith("*"):
            continue
        if ":" in line and not line.startswith("http"):
            k, _, v = line.partition(":")
            k = k.strip().lower().replace(" ", "_")
            v = v.strip().strip('"').strip("'")
            # Skip markdown-style lines
            if k in allowed_keys:
                if v.isdigit():
                    v = int(v)
                elif v.lower() in ("true", "false"):
                    v = v.lower() == "true"
                cfg[k] = v

    return {**defaults, **cfg}

CFG = load_config()

PORT = get_port("NAPOLEON_PORT", int(CFG.get("editor_port", 7700)))
HOST = get("HOST") or get("EDITOR_HOST") or CFG.get("editor_host", "0.0.0.0")
REFRESH_MS = CFG.get("editor_refresh_ms", 2000)  # Default 2 seconds

# Folders to show in sidebar (in order)
FOLDERS_CONFIG = ["sessions", "members_ai", "members", "members_agents"]

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Napoleon Mastermind</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Courier New', monospace; background: #0d0d0d; color: #e0e0e0; display: flex; height: 100vh; overflow: hidden; }

  #sidebar { width: 260px; min-width: 260px; background: #1a1a1a; border-right: 1px solid #333; display: flex; flex-direction: column; overflow-y: auto; }
  #sidebar-title { padding: 14px 16px; font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 2px; border-bottom: 1px solid #333; }
  #loop-controls { padding: 12px 16px; border-bottom: 1px solid #333; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  #start-loop-btn, #stop-loop-btn { padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-family: inherit; }
  #start-loop-btn { background: #3f6b3f; color: #fff; }
  #stop-loop-btn { background: #7a3535; color: #fff; }
  #start-loop-btn:disabled, #stop-loop-btn:disabled { opacity: 0.5; cursor: default; }
  #loop-status { font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 1px; }

  .folder-header { padding: 10px 16px 6px; font-size: 11px; color: #555; text-transform: uppercase; letter-spacing: 1px; margin-top: 6px; display: flex; align-items: center; justify-content: space-between; }
  .folder-header.config-section { color: #7eb8f7; border-top: 1px solid #333; margin-top: 12px; padding-top: 12px; }
  .folder-label { flex: 1; }
  .new-btn { background: none; border: none; color: #444; font-size: 16px; cursor: pointer; padding: 0 2px; line-height: 1; }
  .new-btn:hover { color: #7eb8f7; }

  .file-item { padding: 7px 16px 7px 24px; cursor: pointer; font-size: 12px; color: #999; border-bottom: 1px solid #1e1e1e; transition: background 0.1s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .file-item:hover { background: #222; color: #ddd; }
  .file-item.active { background: #1e2a3a; color: #7eb8f7; border-left: 3px solid #7eb8f7; padding-left: 21px; }
  .file-item.config-file { color: #f7b87e; }
  .file-item.config-file:hover { color: #ffd699; }
  .file-item.config-file.active { background: #2a2a1e; border-left-color: #f7b87e; }

  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #toolbar { padding: 10px 16px; background: #161616; border-bottom: 1px solid #333; display: flex; align-items: center; gap: 12px; }
  #filename { font-size: 13px; color: #7eb8f7; flex: 1; }
  #filename.config { color: #f7b87e; }
  #status { font-size: 12px; color: #666; }
  #save-btn { padding: 6px 18px; background: #2a5298; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; font-family: inherit; }
  #save-btn:hover { background: #3a6bc8; }
  #editor { flex: 1; background: #111; color: #e8e8e8; border: none; outline: none; padding: 20px; font-family: 'Courier New', monospace; font-size: 14px; line-height: 1.7; resize: none; width: 100%; }
  #empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #333; font-size: 15px; }

  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: #1a1a1a; }
  ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-title">Napoleon Mastermind</div>
  <div id="loop-controls">
    <button id="start-loop-btn" onclick="startLoop()">Start</button>
    <button id="stop-loop-btn" onclick="stopLoop()">Stop</button>
    <span id="loop-status">checking...</span>
  </div>
  <div id="tree"></div>
</div>

<div id="main">
  <div id="toolbar">
    <span id="filename">select a file</span>
    <span id="status"></span>
    <button id="save-btn" onclick="saveFile()" style="display:none">Save</button>
  </div>
  <div id="empty">Select a file to edit</div>
  <textarea id="editor" style="display:none" spellcheck="false"></textarea>
</div>

<script>
let currentFile = null;
let stickToBottom = true;

function updateLoopUi(data) {
  const running = !!data.running;
  document.getElementById('loop-status').textContent = running ? `running${data.pid ? ' #' + data.pid : ''}` : 'stopped';
  document.getElementById('loop-status').style.color = running ? '#7edc7e' : '#d28b8b';
  document.getElementById('start-loop-btn').disabled = running;
  document.getElementById('stop-loop-btn').disabled = !running;
}

async function refreshLoopStatus() {
  const r = await fetch('/api/loop/status');
  updateLoopUi(await r.json());
}

async function startLoop() {
  const r = await fetch('/api/loop/start', { method: 'POST' });
  updateLoopUi(await r.json());
}

async function stopLoop() {
  const r = await fetch('/api/loop/stop', { method: 'POST' });
  updateLoopUi(await r.json());
}

function isAtBottom(el) {
  // Allow 50px tolerance
  return el.scrollHeight - el.scrollTop - el.clientHeight < 50;
}

function updateStickToBottom() {
  const editor = document.getElementById('editor');
  stickToBottom = isAtBottom(editor);
}

async function loadTree() {
  const r = await fetch('/api/tree');
  const tree = await r.json();
  const div = document.getElementById('tree');
  div.innerHTML = '';

  // Config section first (special styling)
  if (tree.config && tree.config.length) {
    const header = document.createElement('div');
    header.className = 'folder-header config-section';
    const label = document.createElement('span');
    label.className = 'folder-label';
    label.textContent = '⚙ config';
    header.appendChild(label);
    div.appendChild(header);

    tree.config.forEach(f => {
      const item = document.createElement('div');
      item.className = 'file-item config-file';
      item.textContent = f;
      item.dataset.path = f;
      item.onclick = () => openFile(f);
      if (currentFile === f) item.classList.add('active');
      div.appendChild(item);
    });
  }

  // Regular folders
  for (const [folder, files] of Object.entries(tree)) {
    if (folder === 'config' || folder === 'root') continue;
    if (!files.length) continue;

    const header = document.createElement('div');
    header.className = 'folder-header';

    const label = document.createElement('span');
    label.className = 'folder-label';
    label.textContent = folder + '/';

    const btn = document.createElement('button');
    btn.className = 'new-btn';
    btn.textContent = '+';
    btn.title = 'New file in ' + folder;
    btn.onclick = (e) => { e.stopPropagation(); newFile(folder); };

    header.appendChild(label);
    header.appendChild(btn);
    div.appendChild(header);

    files.forEach(f => {
      const item = document.createElement('div');
      item.className = 'file-item';
      item.textContent = f;
      const path = folder + '/' + f;
      item.dataset.path = path;
      item.onclick = () => openFile(path);
      if (currentFile === path) item.classList.add('active');
      div.appendChild(item);
    });
  }

  // Root files (except config)
  if (tree.root && tree.root.length) {
    const nonConfigRoot = tree.root.filter(f => f !== 'mastermind_config.md');
    if (nonConfigRoot.length) {
      const header = document.createElement('div');
      header.className = 'folder-header';
      const label = document.createElement('span');
      label.className = 'folder-label';
      label.textContent = 'root/';
      header.appendChild(label);
      div.appendChild(header);

      nonConfigRoot.forEach(f => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.textContent = f;
        item.dataset.path = f;
        item.onclick = () => openFile(f);
        if (currentFile === f) item.classList.add('active');
        div.appendChild(item);
      });
    }
  }
}

async function newFile(folder) {
  const name = prompt('New file name (without .md):');
  if (!name) return;
  const path = folder + '/' + name.replace(/\\.md$/, '') + '.md';
  const r = await fetch('/api/file/' + encodeURIComponent(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: '' })
  });
  const data = await r.json();
  if (data.ok) { await loadTree(); openFile(path); }
}

async function openFile(path) {
  const r = await fetch('/api/file/' + encodeURIComponent(path));
  const data = await r.json();
  if (data.error) return;
  const editor = document.getElementById('editor');
  editor.value = data.content;

  const filenameEl = document.getElementById('filename');
  filenameEl.textContent = path;
  filenameEl.className = path === 'mastermind_config.md' ? 'config' : '';

  document.getElementById('empty').style.display = 'none';
  editor.style.display = 'block';
  document.getElementById('save-btn').style.display = 'inline-block';
  document.getElementById('status').textContent = '';
  currentFile = path;
  document.querySelectorAll('.file-item').forEach(el => {
    el.classList.toggle('active', el.dataset.path === path);
  });
  // Scroll to bottom and enable auto-scroll
  stickToBottom = true;
  editor.scrollTop = editor.scrollHeight;
}

async function saveFile() {
  if (!currentFile) return;
  const content = document.getElementById('editor').value;
  const r = await fetch('/api/file/' + encodeURIComponent(currentFile), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  });
  const data = await r.json();
  const status = document.getElementById('status');
  status.textContent = data.ok ? 'saved' : 'error';
  status.style.color = data.ok ? '#5cb85c' : '#d9534f';
  setTimeout(() => status.textContent = '', 2000);
}

async function refreshCurrentFile() {
  if (!currentFile) return;
  const editor = document.getElementById('editor');
  // Don't refresh if user is actively editing (has focus)
  if (document.activeElement === editor) return;

  const r = await fetch('/api/file/' + encodeURIComponent(currentFile));
  const data = await r.json();
  if (data.error) return;

  // Only update if content changed
  if (editor.value !== data.content) {
    editor.value = data.content;
    // Only scroll to bottom if user was already at bottom
    if (stickToBottom) {
      editor.scrollTop = editor.scrollHeight;
    }
    document.getElementById('status').textContent = '↻';
    document.getElementById('status').style.color = '#7eb8f7';
    setTimeout(() => document.getElementById('status').textContent = '', 500);
  }
}

document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveFile(); }
});

// Track scroll position to enable/disable auto-scroll
document.getElementById('editor').addEventListener('scroll', updateStickToBottom);

loadTree();
refreshLoopStatus();
setInterval(loadTree, {{ refresh_ms }});
setInterval(refreshCurrentFile, {{ refresh_ms }});
setInterval(refreshLoopStatus, {{ refresh_ms }});
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML, refresh_ms=REFRESH_MS)


@app.route("/api/tree")
def tree():
    result = {}

    # Config files (special section at top)
    config_files = []
    if CONFIG_FILE.exists():
        config_files.append("mastermind_config.md")
    result["config"] = config_files

    # Standard folders
    for folder in FOLDERS_CONFIG:
        d = BASE_DIR / folder
        result[folder] = sorted(p.name for p in d.glob("*.md")) if d.exists() else []

    # Root .md files
    root_mds = sorted(p.name for p in BASE_DIR.glob("*.md"))
    if root_mds:
        result["root"] = root_mds

    return jsonify(result)


@app.route("/api/file/<path:filepath>", methods=["GET"])
def get_file(filepath):
    path = (BASE_DIR / filepath).resolve()
    if not str(path).startswith(str(BASE_DIR)):
        return jsonify({"error": "forbidden"}), 403
    if not path.exists() or path.suffix != ".md":
        return jsonify({"error": "not found"}), 404
    return jsonify({"content": path.read_text()})


@app.route("/api/file/<path:filepath>", methods=["POST"])
def save_file(filepath):
    path = (BASE_DIR / filepath).resolve()
    if not str(path).startswith(str(BASE_DIR)):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if path.suffix != ".md":
        return jsonify({"ok": False, "error": "only .md allowed"}), 400
    path.parent.mkdir(parents=True, exist_ok=True)
    data = request.get_json()
    path.write_text(data.get("content", ""))
    return jsonify({"ok": True})


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(BASE_DIR, filename)


@app.route("/api/loop/status")
def loop_status():
    return jsonify(get_loop_status())


@app.route("/api/loop/start", methods=["POST"])
def loop_start():
    return jsonify(start_loop())


@app.route("/api/loop/stop", methods=["POST"])
def loop_stop():
    return jsonify(stop_loop())


if __name__ == "__main__":
    print(f"[mastermind_web] http://{HOST}:{PORT}")
    print(f"[mastermind_web] root: {BASE_DIR}")
    print(f"[mastermind_web] Config: {'found' if CONFIG_FILE.exists() else 'not found'}")
    print(f"[mastermind_web] Refresh: {REFRESH_MS}ms")
    app.run(host=HOST, port=PORT, debug=False)
