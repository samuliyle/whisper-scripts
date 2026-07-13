#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime

import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path("/home/samuli/Documents/yt-audio")
SEGMENT_SECONDS = 1800

# Allow overriding browser source without code changes:
#   YTDL_BROWSER=firefox
#   YTDL_BROWSER=brave
#   YTDL_BROWSER='chromium:/home/samuli/.config/BraveSoftware/Brave-Browser:Default'
YTDL_BROWSER = os.environ.get("YTDL_BROWSER", "firefox")


def run_capture(cmd: list[str]) -> str:
    """Run command, capture stdout, raise on error with stderr attached."""
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        # Attach stderr to exception so main() can show it
        raise subprocess.CalledProcessError(
            res.returncode, cmd, output=res.stdout, stderr=res.stderr
        )
    return res.stdout.strip()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: ytdl <video-url>", file=sys.stderr)
        return 1

    url = sys.argv[1]
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    outtmpl = str(
        BASE_DIR
        / f"{date_prefix}_%(id)s_%(title).70s"
        / "%(title).70s.%(ext)s"
    )

    print("Downloading and converting audio…", flush=True)

    yt_dlp_cmd = [
        "yt-dlp",
        "--quiet",
        "--no-warnings",

        # solve YouTube JS challenge (EJS)
        "--remote-components", "ejs:github",

        # avoid "sign in to confirm you're not a bot"
        "--cookies-from-browser", YTDL_BROWSER,

        "-f", "bestaudio",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
        "--print", "after_move:filepath",
        "-o", outtmpl,
        url,
    ]

    print("Running command:")
    print(" ".join(yt_dlp_cmd))
    print(flush=True)

    try:
        wav_path = run_capture(yt_dlp_cmd)
    except subprocess.CalledProcessError as e:
        print("ERROR: yt-dlp failed", file=sys.stderr)

        # Print stderr for easier diagnosis
        if e.stderr:
            err = e.stderr.strip()
            # avoid dumping absurdly long output
            if len(err) > 8000:
                err = err[-8000:]
            print(err, file=sys.stderr)

        return 1

    if not wav_path:
        print("ERROR: yt-dlp did not report output file path", file=sys.stderr)
        return 1

    wav = Path(wav_path)
    if not wav.exists():
        print(f"ERROR: expected WAV not found: {wav}", file=sys.stderr)
        return 1

    out_dir = wav.parent

    print(f"Splitting into {SEGMENT_SECONDS // 60}-minute chunks:", flush=True)
    print(f"  {wav}", flush=True)

    try:
        run([
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(wav),
            "-f", "segment",
            "-segment_time", str(SEGMENT_SECONDS),
            "-c", "copy",
            str(wav.with_suffix("")) + "_part%03d.wav",
        ])
    except subprocess.CalledProcessError:
        print("ERROR: ffmpeg split failed", file=sys.stderr)
        return 1

    wav.unlink()
    print("Done.", flush=True)

    # print directory to stderr for shell wrapper so we can cd to it
    print(out_dir, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
