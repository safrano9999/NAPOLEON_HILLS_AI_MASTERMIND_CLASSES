# NAPOLEON_HILLS_AI_MASTERMIND_CLASSES

Minimal runtime repo for the Napoleon Mastermind FastAPI web UI and persona loop.

## Contents

- `webui.py` starts the editor and loop controls.
- `functions/` contains the runtime logic.
- `members_ai/` contains all AI personas.
- `members/` contains the human member template.
- `sessions/` contains the session template.
- `PROMPT/` contains response directive templates.
- `static/` contains the UI config panel and favicon.

## Runtime Config

Use the same SOT flow as the other safcontainer repos:

```bash
cp env.example .env
cp config.conf_example config.conf
```

Secrets belong in `.env`.
Non-secret runtime and compose settings belong in `config.conf`.

The LLM backend is always an OpenAI-compatible LiteLLM proxy:

- `LITELLM_URL`
- `LITELLM_PORT`
- `LITELLM_API_KEY`
- `NAPOLEON_LITELLM_MODEL`

Direct LiteLLM SDK mode is intentionally not used.

## Run

```bash
python3 -m pip install -r requirements.txt
uvicorn webui:app --host "$FASTAPI_HOST" --port "$NAPOLEON_PORT"
```

In the Fedora container this repo is started by `napoleon.service`.
