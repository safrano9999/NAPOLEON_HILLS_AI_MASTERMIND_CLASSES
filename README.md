# 💰 Napoleon Hill's AI Mastermind 🏦

<p align="center">
  <img src="napoleon_hill.jpg" alt="Napoleon Hill" width="300"/>
</p>

**Napoleon Hill** (1883–1970) was one of the most influential personal success authors in American history. His masterwork, **_Think and Grow Rich_** (1937), remains one of the best-selling books of all time. In **Chapter 10 — The Mastermind**, Hill revealed what he considered the single greatest secret of success: surrounding yourself with a group of brilliant minds aligned toward a common purpose creates an invisible "third mind" far more powerful than any individual.

> *"Whatever the mind of man can conceive and believe, it can achieve."*
> — Napoleon Hill

Hill's legacy is preserved by the **[Napoleon Hill Foundation](https://www.naphill.org/)**, a nonprofit dedicated to bringing his philosophy to people around the world.

---

## 💵 What This Program Does — A Modern AI Mastermind

The program is written in **Python** and lives entirely in **Markdown files** — no database, no web app. Everything is a `.md` file: members, sessions, personas, conversations.

### 🏛️ Three Types of Members

Members are organized in three folders:

- **`members_ai/`** — AI personas. Each file defines a character's identity, philosophy, voice, and worldview. When it's their turn, the supervisor reads their `.md` file and calls the LLM to respond in character. Examples:
  - 🚀 **Elon Musk** — first-principles thinking, moonshot goals, relentless execution
  - 💎 **John D. Rockefeller** — strategy, discipline, long-term wealth building
  - ...and many more in `members_ai/`

- **`members/`** — Human participants. A human member writes their response directly into the session file by hand. The supervisor detects it's a human's turn and waits — it will not proceed until the human has written their entry.

- **`members_agents/`** — Claw agents. These are autonomous agents that read the full session file and know when it is their turn to respond, acting independently within the loop.

### 📜 Sessions

A session is a single Markdown file in `sessions/`. To start one, create a file with this header:

```markdown
# Your Session Title
members: elon_musk, john_rockefeller, your_name
thesis: What is the core question you want the mastermind to tackle?

speaker: elon_musk
```

- `members:` — comma-separated list of participants (must match their `.md` filenames)
- `thesis:` — the question or challenge the group will address
- `speaker:` — who speaks first; the loop picks up from the last `speaker:` line

### ⚙️ The Supervisor Loop

Run `python supervisor_loop.py` and the loop does the rest:

1. Scans all session files in `sessions/`
2. Finds the last `speaker:` line to determine whose turn it is
3. If it's an AI persona — loads their `.md` file, calls the LLM, and appends the response
4. If it's a human — pauses and waits for the human to write their entry
5. Advances to the next member in the list and repeats

The loop sleeps **10 seconds** between cycles by default. You can change this at the top of `supervisor_loop.py`:

```python
SLEEP_SECONDS = 10   # increase for slower pacing, decrease for faster rounds
```

The session file grows turn by turn — a living document you can read, annotate, and version-control.

### 🖥️ Your Experience as a Human Participant

Open the session file in a **Markdown editor with live preview** — [Typora](https://typora.io/), [Obsidian](https://obsidian.md/), or VS Code with the Markdown Preview extension. The file refreshes as the AI members write into it, so you watch the conversation unfold in real time.

When it's your turn, the loop pauses and waits. You'll see your name appear as `speaker: your_name` at the bottom of the file. Just write your response directly below it and save. The loop picks it up automatically and the session continues.

**💸 You don't touch the loop. You don't run any commands. You just write.**

---

## 🚀 Quick Start

```bash
git clone <repo-url>
cd NAPOLEON_HILLS_AI_MASTERMIND_CLASSES
python setup.py
```

Edit `sgpt_config.yaml` with your API key and model, then:

```bash
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows

python supervisor_loop.py
```

---

## 📋 Session File Format

```markdown
# Session Title
members: henry_ford, andrew_carnegie, your_name
thesis: How do I build a business that lasts 100 years?

speaker: henry_ford
[Henry Ford's response here]

speaker: andrew_carnegie
[Carnegie's response here]

speaker: your_name
```

---

> 💰 *"It is literally true that you can succeed best and quickest by helping others to succeed."*
> — Napoleon Hill

*🏦 Built on Napoleon Hill's Mastermind Principle.*
