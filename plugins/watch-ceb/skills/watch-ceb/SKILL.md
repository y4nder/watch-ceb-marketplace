---
name: watch-ceb
description: Watch a video whose speech may be Cebuano (Bisaya) mixed with English. Asks whether the audio is mostly Cebuano; if so, transcribes with Gemini (Whisper large-v3 garbles Cebuano) and takes frames from the stock watch skill; otherwise defers to /watch. Afterwards offers to save the transcript plus an executive summary to a git-versioned, indexed transcripts repo. Use for the user's own recordings, meetings, and DSM/consolidation videos.
argument-hint: "<video-path-or-url> [question]"
allowed-tools: Bash, Read, Write, AskUserQuestion
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
CFG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
WATCH_PY=$(ls -d "$CFG"/plugins/cache/claude-video/watch/*/skills/watch/scripts/watch.py 2>/dev/null | sort -V | tail -1)
# Prefer the installed plugin copy over a personal ~/.claude/skills copy.
CEB_DIR=$(ls -d "$CFG"/plugins/cache/*/watch-ceb/*/skills/watch-ceb/scripts "$CFG"/skills/watch-ceb/scripts 2>/dev/null | head -1)
```

If `WATCH_PY` is empty, tell the user the `watch` plugin isn't installed (`/plugin marketplace add bradautomates/claude-video`, then `/plugin install watch@claude-video`) and stop. If `CEB_DIR` is empty, the `watch-ceb` scripts are missing; stop.

Prerequisites: `ffmpeg`/`ffprobe` on PATH (and `yt-dlp` for URLs). If the transcript script reports they are missing, tell the user to install them.

## Step 3a — "No": stock watch

Read the plugin's `skills/watch/SKILL.md` (sibling of `$WATCH_PY`'s `scripts/` dir) and follow it exactly as if the user had run `/watch`. Stop here.

## Step 3b — "Yes": Gemini transcript + stock frames

Run both, in parallel when possible. Pass the same `--start`/`--end` to both if the user gave a range.

Newer `watch` versions (0.3+) default to `--engine auto`, which uploads the whole video to Gemini whenever `GEMINI_API_KEY` is set and ignores `--no-whisper`. Force local frame extraction when the flag exists:

```bash
ENGINE=$(python3 "$WATCH_PY" --help 2>&1 | grep -q -- '--engine' && echo "--engine local")

# Frames only; Whisper is disabled because it can't handle Cebuano.
python3 "$WATCH_PY" "<source>" $ENGINE --no-whisper [--detail ...] [--start T] [--end T]

# Transcript. Needs a local file: for a URL, use the video file the watch run downloaded
# (its report prints the working dir), or `yt-dlp -f bestaudio -o <tmp>/a.%(ext)s <url>`.
python3 "$CEB_DIR/gemini_transcribe.py" "<local-file>" [--start T] [--end T] --out "<workdir>/transcript.txt"
```

Keep `--out`: Step 4 saves that file, so the transcript isn't retyped.

Key comes from `GEMINI_API_KEY` in the environment or `~/.config/watch/.env` (`GEMINI_MODEL` overrides the model list). If the script exits with "GEMINI_API_KEY not set", tell the user where to get one (https://aistudio.google.com/apikey) and offer to fall back to stock `/watch`.

Then follow the stock skill's Steps 3–5: `Read` every frame in one parallel batch and answer the question (or summarize) citing timestamps. Do Step 4 before cleaning up the working dir (skip cleanup if follow-ups are likely).

## Step 4 — Offer to save the transcript (Gemini path only)

After answering, call `AskUserQuestion`:

- Question: "Save this transcript with an executive summary to the transcripts repo?"
- Options: "Yes, save and push (Recommended)", "Save locally, don't push", "No"

Skip the question if the user already said whether to save. On "No", stop.

On yes:

1. **Executive summary.** Write it in English to `<workdir>/summary.md` with `Write`, from the transcript and frames. Use these headings and drop any that would be empty: **TL;DR** (2–4 bullets), **Decisions**, **Action items** (`- [ ] owner: task`), **Blockers / risks**, **Open questions**. Cite `[MM:SS]` for key points. Mark terms you're unsure of (see "Handling the transcript"). Don't use the summary heading as an H1; the script adds the headings.
2. **Metadata.** Infer it and state it in one line so the user can correct it: title (e.g. "DSM", "Consolidation – Mentorship"), `--type` (one of `dsm`, `meeting`, `consolidation`, `demo`, `recording`, `other`), `--date` (recording date if known from the filename/context, else today), `--tags` (topics/projects/tickets, lowercase, e.g. `growth-portal,gp-263,quiz`), and `--participants` (first names heard).
3. **Save:**

```bash
python3 "$CEB_DIR/save_transcript.py" --transcript "<workdir>/transcript.txt" \
  --summary "<workdir>/summary.md" --title "<title>" --type <type> --date <YYYY-MM-DD> \
  --tags "<a,b>" --participants "<a,b>" --source "<source>" [--no-push]
```

The script writes `<repo>/<YYYY>/<date>-<slug>.md` (frontmatter, then the summary, then the transcript), rebuilds `INDEX.md`, commits, and pushes. Before pushing it switches the active `gh` account to `TRANSCRIPTS_GH_USER` if that isn't the active one. Config comes from env vars or `~/.config/watch/.env`: `TRANSCRIPTS_DIR` (default `~/transcripts`) and `TRANSCRIPTS_GH_USER`.

If it exits with "not a git repo", the repo hasn't been set up yet. Tell the user, and don't create a remote without asking. If the push fails, the commit is still local. Report the error and don't retry with another account.

Report the saved path. To look up old transcripts, read `<repo>/INDEX.md`, or grep the frontmatter: `grep -l '^type: dsm' ~/transcripts/20*/*.md` or `grep -l 'tags:.*gp-263' ...`. Run `save_transcript.py --reindex` after editing files by hand.

## Handling the transcript

- It is Cebuano with English terms left as-is. Answer the user in English unless they write to you in Cebuano. Quote Cebuano lines verbatim and gloss them in English when it matters.
- Gemini can mishear rare words (e.g. "vibe code" came back as "i-five code"/"i-hardcode"). Treat odd terms as uncertain and use the frames and context to sanity-check before stating them as fact.
- If `gemini_transcribe.py` fails after its model fallbacks (503 "high demand" is common), retry once later; otherwise offer frames-only or stock Whisper, and warn that Whisper output will be unreliable for Cebuano.
- Gemini can invent speech for silent, music-only or very noisy audio. If the frames or context show no one talking, or the transcript reads like a scripted conversation that doesn't match the video, say it may be invented. The script drops lines stamped past the end of the audio and warns on stderr; mention that warning if it appears.
- Say in the answer that the transcript source was Gemini, not captions or Whisper.
