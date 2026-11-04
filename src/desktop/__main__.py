"""Open the Scholarships Hunter window: python -m src.desktop [--debug]

Browser preview with real data (no pywebview needed):
    python -m src.desktop --serve [--port 8765] [--no-browser]
"""
import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.desktop")
    parser.add_argument("--debug", action="store_true", help="Enable pywebview debug tools")
    parser.add_argument("--serve", action="store_true",
                        help="Serve the UI to a normal browser on 127.0.0.1 instead of opening a window")
    parser.add_argument("--port", type=int, default=8765, help="Port for --serve (default 8765)")
    parser.add_argument("--no-browser", action="store_true", help="With --serve, do not open a browser")
    args = parser.parse_args(argv)

    if args.serve:
        from .server import serve

        return serve(args.port, open_browser=not args.no_browser)

    import webview  # only the window mode needs pywebview

    from .bridge import Api

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
