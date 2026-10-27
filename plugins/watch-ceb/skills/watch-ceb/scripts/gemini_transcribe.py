#!/usr/bin/env python3
"""Transcribe a video/audio file with Gemini, tuned for Cebuano (Bisaya) mixed with English.

Usage: gemini_transcribe.py <file> [--start T] [--end T] [--speakers "A,B,C"] [--host NAME] [--model M] [--out FILE]
Prints a transcript with absolute [MM:SS] Name: timestamps to stdout. Pure stdlib.
Key: GEMINI_API_KEY from the environment or ~/.config/watch/.env.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
# Tried in order; 503 "high demand" is common on the newest previews.
MODELS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
CHUNK_SECONDS = 600  # 10 min ~ 5 MB of 64 kbps mp3, far under the inline request cap

PROMPT = (
    "Transcribe this audio verbatim. The speakers mix Bisaya/Cebuano with English. "
    "Keep the original language of each phrase; do not translate and do not convert Cebuano "
    "into Tagalog. Keep English words and technical terms in English. "
    "Start a new line with `[MM:SS] Name:` (timestamp relative to the start of this audio) at every "
    "speaker turn, and roughly every 10-15 seconds within a long turn. Name is who is speaking: "
    "identify speakers by voice and by names used when someone is addressed or hands over "
    "(e.g. 'Thanks Joshua. Lawrence?' means Joshua spoke, Lawrence speaks next). A name called at the end of a turn is the NEXT speaker, never the person talking now. "
    "If you cannot tell who is speaking, use 'Speaker A', 'Speaker B' consistently; never guess a name. "
    "Output only the transcript."
)


def build_prompt(speakers: str | None, host: str | None, previous_tail: str | None) -> str:
    prompt = PROMPT
    if speakers:
        prompt += f" Possible participants: {speakers}."
    if host:
        prompt += f" The meeting is run by {host}, who hands over between speakers."
    if previous_tail:
        prompt += (" This audio continues a recording; keep the same speaker names and labels as the "
                   "end of the previous part, which was:\n" + previous_tail)
    return prompt


def load_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env = Path.home() / ".config" / "watch" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("GEMINI_API_KEY not set (env var or ~/.config/watch/.env)")


def to_seconds(t: str | None) -> float | None:
    if t is None:
        return None
    parts = [float(p) for p in t.split(":")]
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


def duration(path: str) -> float:
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        sys.exit("ffmpeg/ffprobe not found on PATH; install ffmpeg (e.g. `sudo pacman -S ffmpeg` or `brew install ffmpeg`)")
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        text=True,
    )
    return float(out.strip())


def extract(path: str, start: float, length: float, dest: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(length), "-i", path,
         "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", dest],
        check=True,
    )


def call(model: str, key: str, audio: bytes, prompt: str) -> str:
    body = json.dumps({"contents": [{"parts": [
        {"text": prompt},
        {"inline_data": {"mime_type": "audio/mp3", "data": base64.b64encode(audio).decode()}},
    ]}]}).encode()
    req = urllib.request.Request(
        ENDPOINT.format(model), data=body,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    data = json.load(urllib.request.urlopen(req, timeout=300))
    return data["candidates"][0]["content"]["parts"][-1]["text"].strip()


def transcribe_chunk(audio: bytes, key: str, models: list[str], prompt: str) -> tuple[str, str]:
    last = None
    for model in models:
        for attempt in range(3):
            try:
                return call(model, key, audio, prompt), model
            except urllib.error.HTTPError as e:
                last = f"{model}: HTTP {e.code}"
                if e.code in (429, 500, 503):
                    time.sleep(5 * (attempt + 1))
                    continue
                break  # 404/400 etc: next model
            except (KeyError, IndexError) as e:
                last = f"{model}: unexpected response ({e!r})"
                break
    sys.exit(f"Gemini transcription failed ({last})")


TS = re.compile(r"\[(\d+):(\d{2})(?::(\d{2}))?\]")


def shift(text: str, offset: float) -> str:
    def fix(m: re.Match) -> str:
        a, b, c = int(m[1]), int(m[2]), m[3]
        secs = (a * 3600 + b * 60 + int(c)) if c else (a * 60 + b)
        secs += int(offset)
        h, rem = divmod(secs, 3600)
        mm, ss = divmod(rem, 60)
        return f"[{h}:{mm:02d}:{ss:02d}]" if h else f"[{mm:02d}:{ss:02d}]"
    return TS.sub(fix, text)


def drop_out_of_range(text: str, limit: float) -> tuple[str, int]:
    """Drop lines stamped past the end of the audio (a sign Gemini invented them)."""
    kept, dropped = [], 0
    for line in text.splitlines():
        m = TS.match(line)
        if m:
            a, b, c = int(m[1]), int(m[2]), m[3]
            secs = (a * 3600 + b * 60 + int(c)) if c else (a * 60 + b)
            if secs > limit + 5:
                dropped += 1
                continue
        kept.append(line)
    return "\n".join(kept), dropped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--speakers", help="comma-separated names of likely participants")
    ap.add_argument("--host", help="who facilitates / hands over between speakers (stand-ups)")
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL"))
    ap.add_argument("--out")
    a = ap.parse_args()

    key = load_key()
    models = [a.model] if a.model else MODELS
    total = duration(a.source)
    start = to_seconds(a.start) or 0.0
    end = min(to_seconds(a.end) or total, total)

    pieces, used = [], None
    with tempfile.TemporaryDirectory() as tmp:
        t = start
        while t < end:
            length = min(CHUNK_SECONDS, end - t)
            mp3 = os.path.join(tmp, "chunk.mp3")
            extract(a.source, t, length, mp3)
            tail = "\n".join(TS.sub("", ln).strip() for ln in pieces[-1].splitlines()[-6:]) if pieces else None
            text, used = transcribe_chunk(Path(mp3).read_bytes(), key, models, build_prompt(a.speakers, a.host, tail))
            pieces.append(shift(text, t))
            t += length

    result, dropped = drop_out_of_range("\n".join(pieces), end)
    if a.out:
        Path(a.out).write_text(result, encoding="utf-8")
    print(f"# Transcript source: gemini ({used}), Cebuano/English prompt")
    if dropped:
        print(
            f"# WARNING: dropped {dropped} line(s) timestamped past the end of the audio; "
            "the transcript may be partly invented",
            file=sys.stderr,
        )
    print(result)


if __name__ == "__main__":
    main()
