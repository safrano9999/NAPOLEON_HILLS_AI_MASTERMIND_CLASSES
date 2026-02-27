# Mastermind Configuration

Settings for the Napoleon Hill AI Mastermind loop.
Edit this file in the web editor (http://127.0.0.1:7700) or any text editor.

---

## Model Settings

default_model: gemini/gemini-flash-latest
Available models (use litellm format):
- Anthropic: claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5
- OpenAI: gpt-4o, gpt-4-turbo, o1
- Gemini: gemini/gemini-3.1-pro-preview
- xAI: xai/grok-2, xai/grok-beta
- Groq: groq/llama3-70b-8192, groq/mixtral-8x7b

---

## Response Settings

response_sentences: 1 short sentence answer!

How many sentences each AI member should speak per turn.
Examples: "2-3", "4-5", "1", "5-7"

---

## Loop Settings

sleep_seconds: 0.01

Seconds to wait between rotation cycles.

---

## Web Editor Settings

Web Editor Settings
editor_host: 127.0.0.1
editor_port: 7700
editor_refresh_ms: 500
How often the file tree refreshes in milliseconds.
Examples: 1000 (1s), 2000 (2s), 5000 (5s)
