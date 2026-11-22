"""Fixed settings. They live in code and the README, never in a file the app writes (R4)."""

from dataclasses import dataclass

# The one model (FT-45): pinned by tag and by digest. A different digest is refused.
MODEL_TAG = "gemma4:e4b"
MODEL_DIGEST = "eb2177adf7646d15faead94fdad6d3e170dc8015653418a3b7d5d52a6380be5b"


@dataclass(frozen=True)
class ModelChoice:
    """A model the user may choose. None of them is Chinese-developed (project rule)."""

    tag: str
    name: str
    maker: str
    download_gb: float
    reads_pictures: bool
    good_for: str
    # The digest the model must have. None: offered, but not yet run through DeskThread's
    # own tests; whatever digest is installed is shown to the user as "not checked by us".
    digest: str | None = None


MODELS: tuple[ModelChoice, ...] = (
    ModelChoice(
        MODEL_TAG, "Gemma 4", "Google", 6.6, True,
        "Best answers. Reads pictures and screenshots.", MODEL_DIGEST,
    ),
    ModelChoice(
        "gemma4:e2b", "Gemma 4 small", "Google", 4.6, True,
        "Faster, needs less memory. Reads pictures and screenshots.",
    ),
    ModelChoice(
        "phi4-mini:latest", "Phi-4 mini", "Microsoft", 2.5, False,
        "Smallest and quickest. Does not read pictures.",
    ),
)  # fmt: skip


def model_choice(tag: str) -> ModelChoice | None:
    return next((m for m in MODELS if m.tag == tag), None)


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
