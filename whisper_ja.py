#!/usr/bin/env python3
from __future__ import annotations

import glob
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


MODEL = Path.home() / ".cache/whisper/ggml-large-v3.bin"
VAD_MODEL = Path.home() / ".cache/whisper/ggml-silero-v6.2.0.bin"
SHIFT_SCRIPT = Path("/home/samuli/Documents/scripts/offset_srt.py")
CHUNK_SECONDS = 1800


def fmt_hms(seconds: float) -> str:
    s = int(round(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


_part_re = re.compile(r"_part(\d+)\.wav$", re.IGNORECASE)


def part_index(path: Path) -> int:
    """
    Extract numeric index from ..._partNNN.wav.
    Falls back to lexicographic order if not found.
    """
    m = _part_re.search(path.name)
    if not m:
        return 10**9
    return int(m.group(1))


def run(cmd: list[str]) -> None:
    """Run a command; raise on failure."""
    subprocess.run(cmd, check=True)


def main() -> int:
    cwd = Path.cwd()
    out = cwd.name + ".srt"
    out_path = cwd / out

    wavs = [Path(p) for p in glob.glob("*_part*.wav")]
    if not wavs:
        print("No chunk WAV files found (*_part*.wav)", file=sys.stderr)
        return 1

    # stable order: numeric part index first, then name tie-breaker
    wavs.sort(key=lambda p: (part_index(p), p.name))

    if not out_path.exists():
        out_path.write_text("", encoding="utf-8")

    total = len(wavs)
    processed = 0
    total_chunk_time = 0.0
    start_all = time.time()

    for i, wav in enumerate(wavs):
        srt = Path(str(wav) + ".srt")  # whisper-cli produces "<file>.wav.srt"
        offset = i * CHUNK_SECONDS

        chunk_start = time.time()

        # --- Transcribe if needed ---
        if srt.exists():
            print(f"Skipping (already transcribed): {srt.name}")
        else:
            print(f"Transcribing: {wav.name}")

            cmd = [
                "whisper-cli",
                "-m", str(MODEL),
                "-f", str(wav),
                "--language", "ja",
                "--output-srt",

                "--max-len", "55",
                "--max-context", "0",

                "--beam-size", "1",
                "--best-of", "1",

                "--temperature", "0",
                "--temperature-inc", "0.2",

                "--logprob-thold", "-0.8",
                "--entropy-thold", "2.4",
                "--no-speech-thold", "0.75",

                "--suppress-nst",
                "--vad",
                "--vad-model", str(VAD_MODEL),
            ]

            try:
                run(cmd)
            except subprocess.CalledProcessError as e:
                print(f"ERROR: whisper-cli failed for {wav.name}", file=sys.stderr)
                return int(e.returncode or 1)

        if not srt.exists():
            print(f"ERROR: Expected subtitle file was not created: {srt.name}", file=sys.stderr)
            return 1

        # --- Incremental merge ---
        print(f"Appending subtitles (offset {offset}s): {srt.name}")
        try:
            # append shifted content directly into OUT
            with out_path.open("a", encoding="utf-8") as out_f:
                subprocess.run(
                    ["python3", str(SHIFT_SCRIPT), str(offset), str(srt)],
                    check=True,
                    stdout=out_f,
                )
                out_f.write("\n")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: offset/merge failed for {srt.name}", file=sys.stderr)
            return int(e.returncode or 1)

        # ETA reporting 
        chunk_elapsed = time.time() - chunk_start
        total_chunk_time += chunk_elapsed
        processed += 1

        remaining = total - processed
        avg = total_chunk_time / processed
        eta = avg * remaining

        print(
            f"Progress: {processed}/{total} | "
            f"last: {fmt_hms(chunk_elapsed)} | "
            f"avg: {fmt_hms(avg)} | "
            f"ETA: {fmt_hms(eta)}"
        )

    # Archive 
    elapsed_all = time.time() - start_all
    print(f"Done. Total time: {fmt_hms(elapsed_all)}")

    chunks_dir = cwd / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    # Move all chunk wavs + wav.srt into chunks/
    for wav in wavs:
        srt = Path(str(wav) + ".srt")
        for p in (wav, srt):
            if p.exists():
                shutil.move(str(p), str(chunks_dir / p.name))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
