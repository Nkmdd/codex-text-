# Beauty Content Factory — Selectel MVP

**Purpose:** source videos/photos from iPhone or Telegram → queued template edit → 1080x1920 MP4 for Reels. Designed for 2 CPU / 4 GB RAM server (one render worker). No claims of AI scene understanding at this stage.

## Available now
- Mobile web uploader behind password; 1–12 photos/videos per job; optional user-provided licensed music.
- Presets: Soft Beauty, Clean Minimal, Bold Editorial; 15/30/45 seconds; title card overlay.
- FFmpeg video/photo join with preserved spoken audio, low-volume optional music, queue status and MP4 download.
- Optional private Telegram bot: `/start`, `/id`, `/new`, `/title`, `/style`, `/duration`, `/make`, `/status`. Bot sends MP4 when ready.
- SQLite job history and persistent Docker volume. Basic health endpoint `/healthz`.

## Important limitations
- **Not AI:** does not yet transcribe speech, automatically pick best semantic moments, remove pauses, add auto captions, score or rewrite reels. These are later additions.
- Telegram Bot API remote file downloads normally limited to 20 MB; large camera clips should go through the **mobile web upload**. For Telegram-delivered outputs over ~45 MB the bot sends a notice instead; use web workflow.
- 1080x1920 CPU encoding can be slow with a 2-core server. One render worker avoids overload; encoding time varies with clips.
- Uploaded source videos and renders are automatically deleted after 7 days once a job completes or fails; job metadata remains. No public signup. Never use copyrighted music without permission.

## Install on existing Selectel Nina Ubuntu 24.04

1. Download this folder or clone repo. Copy it to `/opt/beauty-content-factory` via SSH or GitHub Actions (deploy workflow included). **No need to use Selectel web console.**
2. Copy `.env.example` to `.env` on server; set `WEB_UPLOAD_PASSWORD` to a long random secret (not a token used elsewhere). Keep `.env` only on the server.
3. Set `DOMAIN` to a domain pointed at the server's public IPv4, or `<public-ip>.sslip.io` for testing. In Selectel security rules permit TCP 80/443 inbound, keep SSH (22) restricted to your IP, **do not** open port 8000 to the internet.
4. Run `sudo bash deploy.sh` for local services. Run `PUBLIC=1 sudo -E bash deploy.sh` to start HTTPS Caddy. It will obtain TLS automatically when DNS/ports work.
5. For Telegram, create a separate bot with @BotFather, configure `TELEGRAM_BOT_TOKEN` in server `.env`. Start the bot and send `/start`; it shows numeric user ID. Add allowed IDs to `ALLOWED_TELEGRAM_USERS`; rerun `PUBLIC=1 sudo -E bash deploy.sh`. Nobody is authorized when allowlist is empty.

**GitHub Actions auto-deploy:** This repository includes `deploy.yml`. Copy its workflows to `.github/workflows/` at the repository root, and keep app at `beauty-content-factory/`. Once the first server bootstrap and `.env` are complete, add Actions repository secrets `SELECTEL_HOST`, `SELECTEL_USER`, `SELECTEL_SSH_KEY`, `SELECTEL_KNOWN_HOSTS`, and variable `ENABLE_SELECTEL_DEPLOY=true`. The known-host entry must be verified out-of-band (do not blindly `ssh-keyscan` during deployment). The action uploads source via scp, then runs `deploy.sh` without touching `.env` or persistent Docker volumes. GitHub actions cannot run until those secrets exist.

## Local test

```sh
cp .env.example .env
# Set a local test password; use COOKIE_SECURE=false for localhost only.
docker compose up -d --build web worker
curl http://127.0.0.1:8000/healthz
```

Use `docker compose logs -f worker web` for diagnostics. No Telegram token required for web MVP.

## Architecture

```
phone ─ HTTPS(Caddy) ─ FastAPI ─ SQLite job queue ─ FFmpeg worker ─ MP4 download
                                  ▲                              └─ Telegram delivery
Telegram bot (polling, allowlist) ┘
```

Privacy: password required for browser upload, Telegram ID allowlist for bot, credentials in `.env`, persistent private server volume, HTTPS Caddy, no analytics SDK.
