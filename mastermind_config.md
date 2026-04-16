Mastermind Configuration
Settings for the Napoleon Hill AI Mastermind loop. Edit this file in the web editor (http://127.0.0.1:7700) or any text editor.

Model Settings
default_model: gemini/gemini-flash-latest

Available models (use litellm format):

OpenAI: openai/gpt-5.4
Google: gemini/gemini-flash-latest
xAI: xai/grok-2, xai/grok-beta
Groq: groq/llama3-70b-8192, groq/mixtral-8x7b kilocode/z-ai/glm-5 ✅ kilocode/minimax/minimax-m2.5 ✅
Response Settings
response_sentences: 4-5

How many sentences each AI member should speak per turn. Examples: "2-3", "4-5", "1", "5-7"

Prompt Style
prompt_style: default

Which prompt template to use from PROMPT/. The value matches the filename without `.md`. Add new styles by dropping a new file into PROMPT/.

Loop Settings
sleep_seconds: 1

Seconds to wait between rotation cycles.

Web Editor Settings
Web Editor Settings editor_host: 127.0.0.1 editor_port: 7700 editor_refresh_ms: 5000 How often the file tree refreshes in milliseconds. Examples: 1000 (1s), 2000 (2s), 5000 (5s)
