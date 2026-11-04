"""Open the Scholarships Hunter window: python -m src.desktop [--debug]"""
import argparse
import sys
from pathlib import Path

import webview

from .bridge import Api


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.desktop")
    parser.add_argument("--debug", action="store_true", help="Enable pywebview debug tools")
    args = parser.parse_args(argv)

    index = Path(__file__).resolve().parent / "ui" / "index.html"
    if not index.exists():
        print(f"Warning: UI not found at {index}", file=sys.stderr)

    webview.create_window(
        "Scholarships Hunter",
        url=str(index),
        js_api=Api(),
        width=1280,
        height=820,
        min_size=(1024, 680),
    )
    webview.start(debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
