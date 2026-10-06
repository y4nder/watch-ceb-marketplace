# yander-skills

Claude Code plugin marketplace.

## Install

```
/plugin marketplace add <github-user>/watch-ceb-marketplace
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
2. `yt-dlp` and `ffmpeg` on your PATH.
3. Your own Gemini key (https://aistudio.google.com/apikey):
   ```
   mkdir -p ~/.config/watch && echo 'GEMINI_API_KEY=your-key' >> ~/.config/watch/.env
   ```

## License

MIT — see [LICENSE](LICENSE).
