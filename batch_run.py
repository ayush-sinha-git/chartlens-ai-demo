#!/usr/bin/env python3
"""Run every image in input_data/ through ChartLens AI, saving results to output_data/.

Usage: python batch_run.py
"""

import json
import sys
from pathlib import Path

from chartlens_ai.config import PROJECT_ROOT
from chartlens_ai.exporter import export_to_excel_and_csv
from chartlens_ai.extractor import analyze_chart

INPUT_DIR = PROJECT_ROOT / "input_data"
OUTPUT_DIR = PROJECT_ROOT / "output_data"


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    images = sorted(
        p for p in INPUT_DIR.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")
    )

    if not images:
        print(f"No images found in {INPUT_DIR}")
        return 1

    results = []
    for img_path in images:
        prefix = img_path.stem.replace(" ", "_").replace("&", "and")
        out_prefix = str(OUTPUT_DIR / prefix)
        print(f"\n{'=' * 70}\n{img_path.name}\n{'=' * 70}")
        try:
            parsed = analyze_chart(str(img_path))
            export_to_excel_and_csv(parsed, out_prefix)
            with open(f"{out_prefix}.json", "w") as f:
                json.dump(parsed, f, indent=2)

            di = parsed["data_integrity"]
            meta = parsed["chart_metadata"]
            print(f"  chart_type: {meta['chart_type']}  is_diagram: {meta.get('is_diagram')}")
            print(f"  needs_human_review: {di['needs_human_review']}  confidence: {di['confidence_score']}")
            print(f"  BLUF: {parsed['executive_summary']['bluf']}")
            results.append((img_path.name, "OK"))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((img_path.name, f"ERROR: {e}"))

    print(f"\n\n{'=' * 70}\nSUMMARY\n{'=' * 70}")
    for name, status in results:
        print(f"{name}: {status}")

    return 0 if all(status == "OK" for _, status in results) else 1


if __name__ == "__main__":
    sys.exit(main())
