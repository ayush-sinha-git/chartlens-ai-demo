"""Environment setup: API key, corporate CA bundle, model selection."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: sets vars that aren't already in the environment."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(PROJECT_ROOT / ".env")

# Corporate network (Cloudflare Zero Trust Gateway, or similar TLS-inspecting
# proxy) intercepts HTTPS with a self-signed root CA that Python's certifi
# bundle doesn't trust by default. Point requests/urllib3 at a combined bundle
# (certifi + that root CA) instead of disabling verification. See README for
# how to regenerate certs/combined-ca-bundle.pem on a new machine.
_CA_BUNDLE = PROJECT_ROOT / "certs" / "combined-ca-bundle.pem"
if _CA_BUNDLE.exists():
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_CA_BUNDLE))
    os.environ.setdefault("SSL_CERT_FILE", str(_CA_BUNDLE))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Cost-effective vision model with strong structured-output support on OpenRouter.
# Verified against a diverse set of real financial charts/slides/diagrams:
# gpt-4o-mini and qwen3-vl-30b dropped data points and/or hallucinated flat
# segment values. gemini-2.5-flash and gemini-2.5-pro independently converged
# on consistent, visually-accurate readings — using the cheaper of the two.
# Alternatives: "google/gemini-2.5-pro" (same accuracy, ~4x cost),
# "openai/gpt-4o-mini" (cheaper but materially less accurate on dense charts).
MODEL_ID = os.getenv("GS_CHART_MODEL_ID", "google/gemini-2.5-flash")
