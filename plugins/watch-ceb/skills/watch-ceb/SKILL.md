---
name: watch-ceb
description: Watch a video whose speech may be Cebuano (Bisaya) mixed with English. Asks whether the audio is mostly Cebuano; if so, transcribes with Gemini (Whisper large-v3 garbles Cebuano) and takes frames from the stock watch skill; otherwise defers to /watch. Use for the user's own recordings, meetings, and DSM/consolidation videos.
argument-hint: "<video-path-or-url> [question]"
allowed-tools: Bash, Read, AskUserQuestion
user-invocable: true
---

# /watch-ceb

Wrapper around the `watch` plugin (`bradautomates/claude-video`). It never edits the plugin. It only adds a Gemini transcription step for Cebuano-heavy audio.

## Step 1 — Ask about the language (always, unless the user already said)

Parse the source and any question from the arguments. If the user's message already states the language ("this is Bisaya", "English only"), skip the question and use it. Otherwise call `AskUserQuestion`:

- Question: "Is the speech in this video mostly Cebuano/Bisaya (possibly mixed with English)?"
- Options:
  - "Yes, Cebuano/Bisaya (Recommended)" — use Gemini for the transcript
  - "No, English/other" — use the stock `/watch` flow

## Step 2 — Locate the plugin scripts

```bash
WATCH_PY=$(ls -d ~/.claude/plugins/cache/claude-video/watch/*/skills/watch/scripts/watch.py | sort -V | tail -1)
CEB_DIR=$(ls -d ~/.claude/skills/watch-ceb/scripts ~/.claude/plugins/cache/*/watch-ceb/*/skills/watch-ceb/scripts 2>/dev/null | sort -V | tail -1)
```

If `WATCH_PY` is empty, tell the user the `watch` plugin isn't installed and stop.

## Step 3a — "No": stock watch

Read the plugin's `skills/watch/SKILL.md` (sibling of `$WATCH_PY`'s `scripts/` dir) and follow it exactly as if the user had run `/watch`. Stop here.

## Step 3b — "Yes": Gemini transcript + stock frames

Run both, in parallel when possible. Pass the same `--start`/`--end` to both if the user gave a range.

```bash
# Frames only; Whisper is disabled because it can't handle Cebuano.
python3 "$WATCH_PY" "<source>" --no-whisper [--detail ...] [--start T] [--end T]

# Transcript. Needs a local file: for a URL, use the video file the watch run downloaded
# (its report prints the working dir), or `yt-dlp -f bestaudio -o <tmp>/a.%(ext)s <url>`.
python3 "$CEB_DIR/gemini_transcribe.py" "<local-file>" [--start T] [--end T]
```

Key comes from `GEMINI_API_KEY` in `~/.config/watch/.env`. If the script exits with "GEMINI_API_KEY not set", tell the user where to get one (https://aistudio.google.com/apikey) and offer to fall back to stock `/watch`.

Then follow the stock skill's Steps 3–5: `Read` every frame in one parallel batch, answer the question (or summarize) citing timestamps, and clean up the working dir unless follow-ups are likely.

## Handling the transcript

- It is Cebuano with English terms left as-is. Answer the user in English unless they write to you in Cebuano. Quote Cebuano lines verbatim and gloss them in English when it matters.
- Gemini can mishear rare words (e.g. "vibe code" came back as "i-five code"/"i-hardcode"). Treat odd terms as uncertain and use the frames and context to sanity-check before stating them as fact.
- If `gemini_transcribe.py` fails after its model fallbacks (503 "high demand" is common), retry once later; otherwise offer frames-only or stock Whisper, and warn that Whisper output will be unreliable for Cebuano.
- Say in the answer that the transcript source was Gemini, not captions or Whisper.
