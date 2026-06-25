#!/usr/bin/env python3
"""Import repo Markdown/TOML presets into the Napoleon SQL database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "functions"))

import storage


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Napoleon preset documents into SQL storage")
    parser.add_argument("--force", action="store_true", help="replace existing SQL documents with repo presets")
    parser.add_argument("--if-empty", action="store_true", help="import only when the SQL document table is empty")
    parser.add_argument("--export", action="store_true", help="write SQL documents back to repo files")
    args = parser.parse_args()

    if args.export:
        result = storage.export_to_files()
        print(f"Napoleon SQL export complete: {result.get('exported', 0)} documents.")
        return 0

    result = storage.import_presets(force=args.force)
    if result.get("skipped"):
        print("Napoleon preset import skipped: database already has documents.")
    else:
        print(f"Napoleon preset import complete: {result.get('imported', 0)} documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
