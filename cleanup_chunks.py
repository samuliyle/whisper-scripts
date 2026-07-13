#!/usr/bin/env python3
from __future__ import annotations

import time
from pathlib import Path

BASE_DIR = Path("/home/samuli/Documents/yt-audio")
DAYS_OLD = 7
SECONDS_OLD = DAYS_OLD * 24 * 60 * 60


def is_older_than(path: Path, cutoff: float) -> bool:
    try:
        return path.stat().st_mtime < cutoff
    except FileNotFoundError:
        return False


def is_failed_download_dir(video_dir: Path, cutoff: float) -> bool:
    """
    A failed download directory is defined as:
    - No 'chunks' directory
    - Contains at least one file
    - All files end with '.part'
    - All files are older than cutoff
    """
    if (video_dir / "chunks").exists():
        return False

    files = [p for p in video_dir.iterdir() if p.is_file()]
    if not files:
        return False

    if not all(p.suffix == ".part" for p in files):
        return False

    if not all(is_older_than(p, cutoff) for p in files):
        return False

    return True


def main() -> int:
    if not BASE_DIR.exists():
        print(f"Base directory does not exist: {BASE_DIR}")
        return 1

    now = time.time()
    cutoff = now - SECONDS_OLD

    deleted_files = 0
    deleted_dirs = 0

    for video_dir in BASE_DIR.iterdir():
        if not video_dir.is_dir():
            continue

        # Delete failed download directories 
        if is_failed_download_dir(video_dir, cutoff):
            for p in video_dir.iterdir():
                p.unlink()
                deleted_files += 1
            video_dir.rmdir()
            deleted_dirs += 1
            continue

        chunks_dir = video_dir / "chunks"
        if not chunks_dir.exists():
            continue

        # Delete old chunk files 
        for p in chunks_dir.iterdir():
            if p.is_file() and is_older_than(p, cutoff):
                p.unlink()
                deleted_files += 1

        # Remove chunks/ if empty 
        try:
            if not any(chunks_dir.iterdir()):
                chunks_dir.rmdir()
                deleted_dirs += 1
        except OSError:
            pass

        # Remove video dir if now empty 
        try:
            if not any(video_dir.iterdir()):
                video_dir.rmdir()
                deleted_dirs += 1
        except OSError:
            pass

    print("Cleanup complete:")
    print(f"  Deleted files: {deleted_files}")
    print(f"  Deleted directories: {deleted_dirs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
