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
    # The digest the model must have: the exact version that was tried. The default model was
    # run through the full question set; the other two only through the short smoke test
    # (2026-11-22: Gemma 4 small read the picture and gave valid ids; Phi-4 mini gave valid
    # JSON and, as a text-only model, is never sent pictures). None would mean "not tried".
    digest: str | None = None


MODELS: tuple[ModelChoice, ...] = (
    ModelChoice(
        MODEL_TAG, "Gemma 4", "Google", 6.6, True,
        "Best answers. Reads pictures and screenshots.", MODEL_DIGEST,
    ),
    ModelChoice(
        "gemma4:e2b", "Gemma 4 small", "Google", 4.6, True,
        "Faster, needs less memory. Reads pictures and screenshots.",
        "45d11505b91d888e353859f5deeeeff3ffc9b3aa42263c00904120c53851ef96",
    ),
    ModelChoice(
        "phi4-mini:latest", "Phi-4 mini", "Microsoft", 2.5, False,
        "Smallest and quickest. Does not read pictures.",
        "78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753",
    ),
    # The other families discussed in the plan (5k). Offered for download, NOT tested with
    # DeskThread: no digest is pinned, and none of them reads pictures here. Names and sizes
    # were read from the public model registry on 2026-11-22. No model from a Chinese lab.
    ModelChoice(
        "llama3.1:8b", "Llama 3.1 8B", "Meta", 4.9, False,
        "For everyday questions on a Mac with 16 GB or more",
    ),
    ModelChoice(
        "llama3.2:3b", "Llama 3.2 3B", "Meta", 2.0, False,
        "For quick look-ups on a Mac with little memory",
    ),
    ModelChoice(
        "gpt-oss:20b", "gpt-oss 20B", "OpenAI", 13.8, False,
        "For hard questions when you can wait and have 24 GB or more",
    ),
    ModelChoice(
        "nemotron-mini:4b", "Nemotron Mini", "NVIDIA", 2.7, False,
        "For short questions when speed matters most",
    ),
    ModelChoice(
        "smollm2:1.7b", "SmolLM2", "Hugging Face", 1.8, False,
        "For a first try on an older or very full Mac",
    ),
)  # fmt: skip


def model_choice(tag: str) -> ModelChoice | None:
    return next((m for m in MODELS if m.tag == tag), None)


# Bump on any change to a prompt in app/prompts.py (R5).
PROMPT_VERSION = "p4"  # p4: the prompt says what day it is and how to answer "today"

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
