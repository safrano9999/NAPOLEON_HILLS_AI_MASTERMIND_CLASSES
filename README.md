# 💰 Napoleon Hill's AI Mastermind 🏦

<p align="center">
  <img src="napoleon_hill.jpg" alt="Napoleon Hill" width="300"/>
</p>

**Napoleon Hill** (1883–1970) war einer der einflussreichsten Autoren für persönlichen Erfolg. Sein Meisterwerk **_Think and Grow Rich_** (1937) ist bis heute eines der meistverkauften Bücher aller Zeiten. In **Kapitel 10 — The Mastermind** enthüllte er das größte Erfolgsgeheimnis: Eine Gruppe brillanter Köpfe mit gemeinsamem Ziel erschafft einen unsichtbaren "dritten Verstand", der mächtiger ist als jeder Einzelne.

> *"Whatever the mind of man can conceive and believe, it can achieve."*
> — Napoleon Hill

Hills Vermächtnis wird von der **[Napoleon Hill Foundation](https://www.naphill.org/)** bewahrt.

---

## 🚀 Quick Start — 2 Minuten Setup

```bash
# 1. Repo klonen
git clone <repo-url>
cd NAPOLEON_HILLS_AI_MASTERMIND_CLASSES

# 2. Setup ausführen (erstellt venv + installiert alles)
python3 setup.py

# 3. API-Key eintragen
nano .env   # oder öffne .env in deinem Editor

# 4. Starten!
python3 supervisor_loop.py
```

**Optional — Web-Editor starten:**
```bash
python3 mastermind_web.py
# → öffnet http://127.0.0.1:7700
```

Fertig. Kein venv aktivieren nötig — die Scripts finden es automatisch.

---

## 💵 Was macht das Programm?

Alles läuft in **Markdown-Dateien** — keine Datenbank, kein kompliziertes Setup. Members, Sessions, Personas, Gespräche — alles `.md` Files die du im Browser oder Editor bearbeiten kannst.

### 🏛️ Drei Typen von Members

| Ordner | Typ | Beschreibung |
|--------|-----|--------------|
| `members_ai/` | 🤖 AI Personas | Charaktere mit eigener Persönlichkeit. Loop ruft LLM auf. |
| `members/` | 👤 Menschen | Du schreibst direkt ins Session-File. Loop wartet auf dich. |
| `members_agents/` | 🦾 Agenten | Autonome Agenten die selbstständig agieren. |

**AI Personas Beispiele:**
- 🚀 **Elon Musk** — First-Principles, Moonshots, Execution
- 💎 **John D. Rockefeller** — Strategie, Disziplin, Langzeit-Denken
- 🏭 **Henry Ford** — Massenproduktion, Effizienz, Arbeiterethik
- ...und viele mehr in `members_ai/`

### 📜 Sessions starten

Erstelle eine Datei in `sessions/`:

```markdown
# Meine Business-Idee
members: elon_musk, john_rockefeller, dein_name
thesis: Wie baue ich ein Unternehmen das 100 Jahre hält?

speaker: elon_musk
```

Das war's. Der Loop übernimmt.

---

## ⚙️ Konfiguration

### `.env` — API Keys (privat, nicht im Editor sichtbar)

```bash
# Einen Key auskommentieren und eintragen:
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=...
```

### `mastermind_config.md` — Einstellungen (im Web-Editor editierbar!)

```markdown
default_model: gemini/gemini-2.0-flash
response_sentences: 4-5
sleep_seconds: 0.5
editor_refresh_ms: 2000
```

| Setting | Beschreibung | Beispiele |
|---------|--------------|-----------|
| `default_model` | Welches LLM | `gemini/gemini-2.0-flash`, `anthropic/claude-sonnet-4-6`, `openai/gpt-4o` |
| `response_sentences` | Antwortlänge | `2-3`, `4-5`, `1`, `5-7` |
| `sleep_seconds` | Pause zwischen Zyklen | `0.5`, `1`, `10` |
| `editor_refresh_ms` | Browser-Refresh | `1000`, `2000`, `500` |

**Live-Editing:** Änderungen werden sofort übernommen, kein Neustart nötig!

---

## 🖥️ Web-Editor

```bash
python3 mastermind_web.py
# → http://127.0.0.1:7700
```

<p align="center">
  <img src="editor_screenshot.png" alt="Web Editor" width="600"/>
</p>

**Features:**
- 📁 Alle Sessions, Members und Config an einem Ort
- 🔄 Auto-Refresh — sieh zu wie AI-Antworten reinkommen
- 📜 Smart-Scroll — bleibt unten wenn du unten bist
- ⚙️ Config direkt im Browser editieren
- 💾 Speichern mit `Ctrl+S` / `Cmd+S`

---

## 🎯 Deine Experience als Mensch

1. **Öffne den Web-Editor** oder die Session in deinem Lieblings-Markdown-Editor
2. **Schau zu** wie die AI-Members diskutieren
3. **Wenn du dran bist** — schreib einfach unter `speaker: dein_name`
4. **Speichern** — der Loop macht automatisch weiter

**💸 Du tippst keinen Code. Du schreibst einfach.**

---

## 📁 Projektstruktur

```
NAPOLEON_HILLS_AI_MASTERMIND_CLASSES/
├── .env                    # 🔑 API Keys (privat)
├── mastermind_config.md    # ⚙️ Einstellungen (editierbar)
├── supervisor_loop.py      # 🔄 Der Haupt-Loop
├── mastermind_web.py       # 🌐 Web-Editor
├── setup.py                # 📦 Installation
├── rules.md                # 📜 Globale Regeln für alle
├── members_ai/             # 🤖 AI Personas
│   ├── elon_musk.md
│   ├── john_rockefeller.md
│   └── ...
├── members/                # 👤 Menschen
│   └── dein_name.md
├── members_agents/         # 🦾 Agenten
└── sessions/               # 💬 Gespräche
    └── meine_session.md
```

---

## 🔧 Unterstützte LLM Provider

Läuft auf **[litellm](https://docs.litellm.ai/)** — alle großen Provider:

| Provider | Model-Format | Beispiel |
|----------|--------------|----------|
| Anthropic | `anthropic/...` | `anthropic/claude-sonnet-4-6` |
| OpenAI | `openai/...` | `openai/gpt-4o` |
| Google | `gemini/...` | `gemini/gemini-2.0-flash` |
| xAI | `xai/...` | `xai/grok-2` |
| Groq | `groq/...` | `groq/llama3-70b-8192` |

---

## 💡 Tipps

- **Schnellere Runden?** → `sleep_seconds: 0.25`
- **Längere Antworten?** → `response_sentences: 6-8`
- **Anderes Model testen?** → Einfach in Config ändern, wird live übernommen
- **Mehrere Sessions parallel?** → Leg einfach mehr Files in `sessions/` an

---

> 💰 *"It is literally true that you can succeed best and quickest by helping others to succeed."*
> — Napoleon Hill

*🏦 Built on Napoleon Hill's Mastermind Principle.*
