"""CLI entrypoint: python -m chartlens_ai <image_path_or_url> [output_prefix]"""

import json
import sys
from pathlib import Path

from .config import MODEL_ID, PROJECT_ROOT
from .exporter import export_to_excel_and_csv
from .extractor import analyze_chart

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output_data"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if len(argv) < 1:
        print("Usage: python -m chartlens_ai <path_to_image_or_url> [output_prefix]")
        return 1

    image_input = argv[0]
    prefix = argv[1] if len(argv) > 1 else str(DEFAULT_OUTPUT_DIR / Path(image_input).stem)

    print(f"Analyzing '{image_input}' via OpenRouter ({MODEL_ID})...")
    parsed_json = analyze_chart(image_input)

    print("\n--- EXTRACTED JSON ---")
    print(json.dumps(parsed_json, indent=2))

    if parsed_json["data_integrity"]["needs_human_review"]:
        print("\n[!] WARNING: Human review flagged due to:", parsed_json["data_integrity"]["missing_elements"])

    DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
    export_to_excel_and_csv(parsed_json, output_prefix=prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
