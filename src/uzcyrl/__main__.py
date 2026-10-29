"""Command line: python -m uzcyrl [--latin] [TEXT ...] (reads stdin when no text is given)."""
from __future__ import annotations

import argparse
import sys

from . import __version__, to_cyrillic, to_latin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uzcyrl", description="Uzbek Latin ↔ Cyrillic transliteration.")
    parser.add_argument("text", nargs="*", help="text to convert (default: read from stdin)")
    parser.add_argument("--latin", action="store_true", help="convert Cyrillic to Latin instead")
    parser.add_argument("--version", action="version", version=f"uzcyrl {__version__}")
    args = parser.parse_args(argv)

    # Windows consoles default to a legacy code page that cannot print Cyrillic or oʻ.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    convert = to_latin if args.latin else to_cyrillic
    if args.text:
        print(convert(" ".join(args.text)))
        return 0
    for line in sys.stdin:
        sys.stdout.write(convert(line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
