"""Fixed settings. They live in code and the README, never in a file the app writes (R4)."""

# The one model (FT-45): pinned by tag and by digest. A different digest is refused.
MODEL_TAG = "gemma4:e4b"
MODEL_DIGEST = "eb2177adf7646d15faead94fdad6d3e170dc8015653418a3b7d5d52a6380be5b"
# Bump on any change to a prompt in app/prompts.py (R5).
PROMPT_VERSION = "p2"

LOOPBACK = "127.0.0.1"
# Our own model server port, so it is never confused with an Ollama the user runs themselves.
MODEL_PORT = 11435
MODEL_KEEP_ALIVE = "30m"
MODEL_SEED = 7

# Environment for every child process: telemetry and cloud features off (R3, N-5).
QUIET_ENV: dict[str, str] = {
    "OLLAMA_HOST": f"{LOOPBACK}:{MODEL_PORT}",
    "OLLAMA_NO_CLOUD": "1",
    "OLLAMA_KEEP_ALIVE": MODEL_KEEP_ALIVE,
    "DO_NOT_TRACK": "1",
    "NEXT_TELEMETRY_DISABLED": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}
