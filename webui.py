#!/usr/bin/env python3
"""
webui.py — Napoleon Hill Mastermind web editor.
Lives in the project root. Shows all .md files across all folders.
Config via config/mastermind_config.toml.
Run: python3 webui.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "functions"))

from python_header import get, get_port  # noqa: F401 — loads .env

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template

import core

BASE_DIR = core.BASE_DIR
TOML_CONFIG = core.TOML_CONFIG
MEMBERS_AI = core.MEMBERS_AI

CFG = core.load_config()

PORT = get_port("NAPOLEON_PORT", int(CFG.get("editor_port", 7700)))
HOST = get("HOST") or get("EDITOR_HOST") or CFG.get("editor_host", "0.0.0.0")
REFRESH_MS = CFG.get("editor_refresh_ms", 2000)

# Folders to show in sidebar (in order)
FOLDERS_CONFIG = ["sessions", "members_ai", "members", "members_agents"]

app = FastAPI()

# Static files
_static_dir = BASE_DIR / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

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
  #tabs { display: flex; border-bottom: 1px solid #333; background: #161616; }
  .tab { padding: 8px 20px; background: none; border: none; border-bottom: 2px solid transparent; color: #888; cursor: pointer; font-family: inherit; font-size: 13px; }
  .tab:hover { color: #ddd; }
  .tab.active { color: #7eb8f7; border-bottom-color: #7eb8f7; }
  #editor-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #config-view { flex: 1; overflow-y: auto; display: none; }
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
  <div id="tabs">
    <button class="tab active" onclick="switchTab('editor')">Editor</button>
    <button class="tab" onclick="switchTab('config')">Configuration</button>
  </div>
  <div id="editor-view">
    <div id="toolbar">
      <span id="filename">select a file</span>
      <span id="status"></span>
      <button id="save-btn" onclick="saveFile()" style="display:none">Save</button>
    </div>
    <div id="empty">Select a file to edit</div>
    <textarea id="editor" style="display:none" spellcheck="false"></textarea>
  </div>
  <div id="config-view"></div>
</div>

<script>
let currentFile = null;
let stickToBottom = true;
let configLoaded = false;

function encodePath(p) {
  return p.split('/').map(encodeURIComponent).join('/');
}

function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('editor-view').style.display = tab === 'editor' ? 'flex' : 'none';
  document.getElementById('config-view').style.display = tab === 'config' ? 'block' : 'none';
  if (tab === 'config' && !configLoaded) {
    fetch('/static/config.html').then(r => r.text()).then(html => {
      document.getElementById('config-view').innerHTML = html;
      configLoaded = true;
      if (typeof initConfig === 'function') initConfig();
    });
  }
}

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

  if (tree.root && tree.root.length) {
    const nonConfigRoot = tree.root;
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
  const r = await fetch('/api/file/' + encodePath(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: '' })
  });
  const data = await r.json();
  if (data.ok) { await loadTree(); openFile(path); }
}

async function openFile(path) {
  const r = await fetch('/api/file/' + encodePath(path));
  const data = await r.json();
  if (data.error) return;
  const editor = document.getElementById('editor');
  editor.value = data.content;

  const filenameEl = document.getElementById('filename');
  filenameEl.textContent = path;
  filenameEl.className = path.startsWith('config/') ? 'config' : '';

  document.getElementById('empty').style.display = 'none';
  editor.style.display = 'block';
  document.getElementById('save-btn').style.display = 'inline-block';
  document.getElementById('status').textContent = '';
  currentFile = path;
  document.querySelectorAll('.file-item').forEach(el => {
    el.classList.toggle('active', el.dataset.path === path);
  });
  stickToBottom = true;
  editor.scrollTop = editor.scrollHeight;
}

async function saveFile() {
  if (!currentFile) return;
  const content = document.getElementById('editor').value;
  const r = await fetch('/api/file/' + encodePath(currentFile), {
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
  if (document.activeElement === editor) return;

  const r = await fetch('/api/file/' + encodePath(currentFile));
  const data = await r.json();
  if (data.error) return;

  if (editor.value !== data.content) {
    editor.value = data.content;
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

_html_template = Template(HTML)


@app.get("/", response_class=HTMLResponse)
def index():
    return _html_template.render(refresh_ms=REFRESH_MS)


@app.get("/api/tree")
def tree():
    result = {}

    # Config files (special section at top)
    config_files = []
    if TOML_CONFIG.exists():
        config_files.append("config/mastermind_config.toml")
    result["config"] = config_files

    # Standard folders
    for folder in FOLDERS_CONFIG:
        d = BASE_DIR / folder
        result[folder] = sorted(p.name for p in d.glob("*.md")) if d.exists() else []

    # Root .md files
    root_mds = sorted(p.name for p in BASE_DIR.glob("*.md"))
    if root_mds:
        result["root"] = root_mds

    return result


@app.get("/api/file/{filepath:path}")
def get_file(filepath: str):
    path = (BASE_DIR / filepath).resolve()
    if not path.is_relative_to(BASE_DIR):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not path.exists() or path.suffix not in (".md", ".toml"):
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"content": path.read_text()}


@app.post("/api/file/{filepath:path}")
async def save_file(filepath: str, request: Request):
    path = (BASE_DIR / filepath).resolve()
    if not path.is_relative_to(BASE_DIR):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    if path.suffix not in (".md", ".toml"):
        return JSONResponse({"ok": False, "error": "only .md/.toml allowed"}, status_code=400)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = await request.json()
    path.write_text(data.get("content", ""))
    return {"ok": True}


_ASSETS_DIR = BASE_DIR / "assets"
_SAFE_ASSET_EXT = {".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico",
                   ".woff", ".woff2", ".ttf", ".eot"}


@app.get("/assets/{filename:path}")
def assets(filename: str):
    target = (_ASSETS_DIR / filename).resolve()
    if not target.is_relative_to(_ASSETS_DIR) or not target.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    if target.suffix.lower() not in _SAFE_ASSET_EXT:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(target)


@app.get("/api/config")
def api_get_config():
    return core.get_config()


@app.post("/api/config")
async def api_save_config(request: Request):
    core.save_config(await request.json())
    return {"ok": True}


@app.get("/api/member/{name}")
def api_get_member(name: str):
    result = core.get_member(name)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return result


@app.post("/api/member/{name}")
async def api_save_member(name: str, request: Request):
    data = await request.json()
    result = core.save_member(name, data.get("content", ""))
    if "error" in result:
        return JSONResponse(result, status_code=403)
    return result


@app.get("/api/prompt/{name}")
def api_get_prompt(name: str):
    result = core.get_prompt(name)
    if "error" in result:
        return JSONResponse(result, status_code=404)
    return result


@app.post("/api/prompt/{name}")
async def api_save_prompt(name: str, request: Request):
    data = await request.json()
    result = core.save_prompt(name, data.get("content", ""))
    if "error" in result:
        return JSONResponse(result, status_code=403)
    return result


@app.get("/api/models")
def api_list_models():
    return core.discover_models()


@app.get("/api/check")
def api_check_deps():
    return core.check_connections()


@app.get("/api/loop/status")
def api_loop_status():
    return core.loop_status()


@app.post("/api/loop/start")
def api_loop_start():
    return core.loop_start()


@app.post("/api/loop/stop")
def api_loop_stop():
    return core.loop_stop()


if __name__ == "__main__":
    print(f"[mastermind_web] http://{HOST}:{PORT}")
    print(f"[mastermind_web] root: {BASE_DIR}")
    print(f"[mastermind_web] Config: {'found' if TOML_CONFIG.exists() else 'not found'}")
    print(f"[mastermind_web] Refresh: {REFRESH_MS}ms")
    uvicorn.run(app, host=HOST, port=PORT)
