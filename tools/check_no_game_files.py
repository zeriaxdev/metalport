#!/usr/bin/env python3
"""Fail if the repository or a release ZIP contains anything from a game, Unity or Valve.

    python3 tools/check_no_game_files.py              # files tracked by git
    python3 tools/check_no_game_files.py --zip X.zip  # a release archive

Games are paid, and Unity and Steam binaries are not ours to distribute (see THIRD-PARTY-NOTICES.md).
Adapted from zeriaxdev/buckshot-roulette-mac (same owner, MIT).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import PurePosixPath

FORBIDDEN_SUFFIXES = {
    ".exe", ".dll", ".dylib", ".so", ".a", ".dmg", ".pkg",
    ".assets", ".ress", ".resource", ".bundle", ".unity3d", ".sharedassets", ".resourcefile",
    ".ogg", ".wav", ".mp3", ".mp4", ".webm", ".ttf", ".otf", ".icns",
}
FORBIDDEN_PARTS = {"ports", "work", ".cache", ".venv"}
MAX_BYTES = 2 * 1024 * 1024


def problems(entries: list[tuple[str, int]]) -> list[str]:
    found = []
    for name, size in entries:
        path = PurePosixPath(name)
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            found.append(f"{name}: {suffix} files are game, engine or media files")
        elif path.name in {"globalgamemanagers", "unity default resources"} or path.name.startswith("level") and suffix == "":
            found.append(f"{name}: Unity data file")
        elif set(path.parts) & FORBIDDEN_PARTS or any(part.endswith(".app") for part in path.parts):
            found.append(f"{name}: inside a build or work folder")
        elif size > MAX_BYTES:
            found.append(f"{name}: {size // 1024} KB is larger than anything this project ships")
    return found


def tracked_files() -> list[tuple[str, int]]:
    names = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True).stdout.decode().split("\0")
    return [(name, os.path.getsize(name) if os.path.exists(name) else 0) for name in names if name]


def zip_entries(path: str) -> list[tuple[str, int]]:
    with zipfile.ZipFile(path) as archive:
        return [(info.filename, info.file_size) for info in archive.infolist() if not info.is_dir()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", help="check this release ZIP instead of the git checkout")
    args = parser.parse_args()
    entries = zip_entries(args.zip) if args.zip else tracked_files()
    found = problems(entries)
    for line in found:
        print(f"NOT ALLOWED: {line}")
    print(f"checked {len(entries)} files: {'FAILED' if found else 'no game files found'}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
