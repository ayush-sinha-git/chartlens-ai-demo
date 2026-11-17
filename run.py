#!/usr/bin/env python3
"""Convenience wrapper: python run.py <image_path_or_url> [output_prefix]"""

import sys

from chartlens_ai.cli import main

if __name__ == "__main__":
    sys.exit(main())
