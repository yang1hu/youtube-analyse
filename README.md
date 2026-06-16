# YouTube Creator Agent

A local-first workspace for analyzing YouTube videos, extracting reusable creator patterns, and turning those patterns into idea cards, style profiles, and script drafts.

The project combines a FastAPI backend with a React/Vite frontend. It is designed for personal research workflows: configure channels, collect recent uploads, analyze videos with transcripts and an OpenAI-compatible LLM, translate scripts, maintain a sample library, and generate draft scripts from reusable ideas.

> This is not an official YouTube product. Use it responsibly and avoid high-frequency collection that may trigger platform rate limits.

## Features

- Channel monitoring and recent upload sync.
- Browser-based YouTube metadata collection with Playwright, DrissionPage, or CDP.
- Transcript/subtitle collection with `yt-dlp` and `youtube-transcript-api`.
- LLM-first video analysis with a rule-based fallback.
- Video report pages with transcript evidence and cached Chinese translation.
- Idea Lab for reusable idea cards and complete outline briefs.
- Sample Library for first-five-minute opening analysis, tags, notes, and multi-sample style merging.
- Style Library for learning reusable script styles from reports or samples.
- Script Studio for generating, rewriting, editing, versioning, and exporting script drafts.
- Task Center with optional Redis queue support and manual fallback.
- Optional MySQL snapshot storage for workspace data.
- Local health checks for browser, LLM, Redis, MySQL, cache paths, and media tooling.

## Architecture

```text
frontend/        React 19 + Vite workspace UI
backend/         FastAPI service, agent runtime, collectors, task services
scripts/         Local development helper scripts
docs/            Product and implementation notes
```

Runtime state is local by default:

- `backend/.env` stores local secrets and environment overrides.
- `backend/.runtime/workspace-settings.json` stores settings saved from the UI.
- `backend/.runtime/workspace-data.json` stores local workspace data.
- `backend/.runtime/logs/analysis.jsonl` stores audit events without API keys.
- `backend/.runtime/transcripts/` stores transcript cache files.
- `backend/.runtime/translations/` stores translation cache files.
- `backend/.runtime/samples/` stores local sample assets.

These paths are ignored by Git and should not be committed.

## Requirements

- Python 3.11+
- Node.js 20+
- Chromium browser support for Playwright, DrissionPage, or CDP collection
- Optional: Redis for background task queue
- Optional: MySQL for snapshot storage
- Optional: ffmpeg for media/sample workflows

## Quick Start

Clone the repository and start the local development stack:

```powershell
git clone https://github.com/yang1hu/youtube-analyse.git
cd youtube-analyse
.\scripts\start-dev.ps1
```

Open:

```text
http://127.0.0.1:5173
```

The script starts:

- Backend API on `http://127.0.0.1:8001`
- Frontend dev server on `http://127.0.0.1:5173`
- Optional task worker process

Override the backend port if needed:

```powershell
$env:YCA_API_PORT="8000"
$env:VITE_API_TARGET="http://127.0.0.1:8000"
.\scripts\start-dev.ps1
```

## Backend Setup

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m playwright install chromium
python -m uvicorn creator_agent.main:app --host 127.0.0.1 --port 8001
```

Run the worker separately when not using `scripts/start-dev.ps1`:

```powershell
cd backend
python -m creator_agent.worker
```

If Redis is unavailable, queued tasks remain visible in Task Center and can be run manually from the UI.

## Frontend Setup

```powershell
cd frontend
npm install
$env:VITE_API_TARGET="http://127.0.0.1:8001"
npm run dev -- --host 127.0.0.1 --port 5173
```

The frontend proxies `/api` to `VITE_API_TARGET`.

## Configuration

Most settings can be saved from the Settings page:

- YouTube channel URLs
- Browser collection engine
- Browser/CDP connection settings
- LLM base URL
- Analysis model
- Translation model
- LLM API key
- Monitor interval and auto-analysis controls

Environment fallbacks are also supported:

```powershell
$env:YCA_OPENAI_BASE_URL="https://your-openai-compatible-endpoint/v1"
$env:YCA_OPENAI_ANALYSIS_MODEL="your-analysis-model"
$env:YCA_OPENAI_TRANSLATION_MODEL="your-translation-model"
$env:YCA_OPENAI_API_KEY="your-local-secret"
```

Do not commit `backend/.env` or any file under `backend/.runtime/`.

## Storage

Local JSON storage is the default. To use MySQL snapshot storage, set:

```powershell
$env:YCA_DATABASE_URL="mysql+pymysql://user:password@localhost:3306/youtube_creator_agent"
```

If `YCA_WORKSPACE_DATA_PATH` is set, the app uses JSON storage even when `YCA_DATABASE_URL` exists.

## Security

This app is intended to run on a trusted local machine.

- The backend has no user authentication.
- The LLM API key is stored only in local runtime settings.
- `/api/settings` returns `openai_api_key_set`, not the key value.
- The backend rejects non-local `Host` headers by default.
- Keep the API bound to `127.0.0.1`.

To intentionally run behind your own trusted access control:

```powershell
$env:YCA_ALLOW_REMOTE_ACCESS="true"
```

## Development

Run backend tests:

```powershell
cd backend
python -m pytest -q
```

Build the frontend:

```powershell
cd frontend
npm run build
```

Useful frontend command:

```powershell
cd frontend
npm run type-check
```

## Notes

- Comment collection is currently a reserved interface and returns `not_configured`.
- YouTube collection depends on page structure and external tooling, so occasional breakage is expected.
- Avoid repeatedly testing collection against many videos in a short time.
- For best results, configure an OpenAI-compatible LLM endpoint before running video analysis.
