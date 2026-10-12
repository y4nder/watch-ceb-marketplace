# yander-skills

Claude Code plugin marketplace.

## Install

```
/plugin marketplace add y4nder/watch-ceb-marketplace
/plugin install watch-ceb@yander-skills
```

## watch-ceb

`/watch-ceb <video-path-or-url> [question]` — transcribes Cebuano/English videos with Gemini
(Whisper large-v3 garbles Cebuano) and takes frames via the stock watch skill.

### Prerequisites

1. The stock watch plugin:
   ```
   /plugin marketplace add bradautomates/claude-video
   /plugin install watch@claude-video
   ```
2. `ffmpeg` (with `ffprobe`) on your PATH, plus `yt-dlp` if you pass URLs.
3. Your own Gemini key (https://aistudio.google.com/apikey):
   ```
   mkdir -p ~/.config/watch && echo 'GEMINI_API_KEY=your-key' >> ~/.config/watch/.env
   ```
   The stock `watch` plugin also picks this key up, which is why the skill forces `--engine local` for frames.

### Notes

- Gemini can invent speech for silent or music-only audio; the script drops timestamps past the end of the clip and warns.
- `GEMINI_MODEL` overrides the built-in model list.

### Saving transcripts (optional)

When it's done, the skill offers to save the transcript with an executive summary into a git repo you own. Each save writes `YYYY/YYYY-MM-DD-<slug>.md` (frontmatter with type, tags and participants, then the summary, then the transcript), rebuilds `INDEX.md`, commits, and pushes. Setup:

```
mkdir ~/transcripts && cd ~/transcripts && git init -b main   # add a private remote if you want pushes
echo 'TRANSCRIPTS_DIR=~/transcripts' >> ~/.config/watch/.env
echo 'TRANSCRIPTS_GH_USER=<gh-account>' >> ~/.config/watch/.env  # optional: gh account to switch to before pushing
```

## License

MIT — see [LICENSE](LICENSE).
