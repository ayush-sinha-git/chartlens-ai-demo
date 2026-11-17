"""Image encoding and the OpenRouter vision API call."""

import base64
import json
import mimetypes
import time
from pathlib import Path

import requests

from .config import MODEL_ID, OPENROUTER_API_KEY, OPENROUTER_URL
from .prompts import SYSTEM_PROMPT
from .schema import JSON_SCHEMA
from .validation import check_bluf_consistency


def encode_image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "image/png"

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def analyze_chart(image_source: str, max_retries: int = 2) -> dict:
    if not OPENROUTER_API_KEY:
        raise ValueError("Missing OPENROUTER_API_KEY environment variable.")

    # Support either a public HTTP(S) image URL or a local file path
    if image_source.startswith(("http://", "https://")):
        image_url = image_source
    else:
        image_url = encode_image_to_data_url(image_source)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost:3000",  # Optional OpenRouter app ranking header
        "X-Title": "ChartLens AI - GS Pitchbook & Chart Analyzer",
    }

    payload = {
        "model": MODEL_ID,
        "temperature": 0.0,  # Deterministic extraction
        "max_tokens": 16000,  # Generous cap: dense multi-series charts (e.g. scatter plots with
        # many points/categories) can produce long extracted_data + anomaly/summary text
        "provider": {
            "require_parameters": True  # Only route to endpoints supporting strict json_schema
        },
        "plugins": [
            {"id": "response-healing"}  # Auto-repairs minor JSON syntax issues if any occur
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "chartlens_ai",
                "strict": True,
                "schema": JSON_SCHEMA,
            },
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Deconstruct this financial visual and extract all data series, metadata, risks, and the BLUF executive summary.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            },
        ],
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
            if not response.ok:
                # Retry on transient server-side errors, fail fast on client errors (4xx)
                if response.status_code >= 500 and attempt < max_retries:
                    last_error = RuntimeError(f"OpenRouter API error {response.status_code}: {response.text}")
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"OpenRouter API error {response.status_code}: {response.text}")

            result = response.json()
            choice = result["choices"][0]

            if choice.get("finish_reason") == "length":
                # Observed to be intermittent on dense charts (same request often
                # succeeds on retry), so retry before giving up.
                last_error = RuntimeError(
                    "Model output was truncated at the max_tokens limit. "
                    "Try increasing max_tokens or simplifying the chart."
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_error

            raw_content = choice["message"]["content"]
            parsed = json.loads(raw_content)
            parsed["_validation_warnings"] = check_bluf_consistency(parsed)
            return parsed

        except requests.exceptions.Timeout as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"OpenRouter request timed out after {max_retries + 1} attempts: {e}")

    raise last_error
