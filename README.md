# YouTube Creator Growth Agent

Standalone local app for monitoring one YouTube channel, collecting recent videos, fetching scripts/subtitles, and turning a video into an LLM-based creator analysis report and reusable idea cards.

The app is isolated from Hermes core. It uses a FastAPI backend, local JSON runtime storage by default for the current MVP, optional MySQL/Redis-ready models for later, and a React/Vite frontend.

## Quick Start

```powershell
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent
.\scripts\start-dev.ps1
```

Open `http://127.0.0.1:5173`.

The development backend defaults to `http://127.0.0.1:8001` because `8000` is often occupied by other local services. You can override it:

```powershell
$env:YCA_API_PORT="8000"
$env:VITE_API_TARGET="http://127.0.0.1:8000"
.\scripts\start-dev.ps1
```

## Backend

```powershell
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/backend
python -m pip install -e ".[dev]"
python -m playwright install chromium
python -m pytest -q
python -m uvicorn creator_agent.main:app --host 127.0.0.1 --port 8001
```

Optional task worker:

```powershell
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/backend
python -m creator_agent.worker
```

The worker consumes Redis task IDs and also runs the channel monitor when it is due. If Redis is unavailable, tasks stay visible in Task Center and can be run manually from the UI.

`scripts/start-dev.ps1` starts the worker together with the backend and frontend. Run the worker manually only when you start services one by one.

Important runtime files:

- `backend/.env`: local secrets and LLM defaults. This file is ignored by git.
- `backend/.runtime/workspace-settings.json`: channel, browser, and LLM settings saved from the Settings page.
- `backend/.runtime/workspace-data.json`: channels, recent videos, jobs, reports, and idea cards.
- `backend/.runtime/logs/analysis.jsonl`: append-only analysis audit log with task IDs, analyzed video URLs, tool request summaries, LLM request/response summaries, and final report status. API keys are not written.
- `backend/.runtime/transcripts/`: saved raw scripts/subtitles.
- `backend/.runtime/translations/`: cached Chinese translations.

Local JSON storage is the default. To opt into MySQL snapshot storage, set `YCA_DATABASE_URL` before starting the backend, for example `mysql+pymysql://creator_agent:creator_agent@localhost:3306/creator_agent`.

You can save LLM and browser settings before choosing a channel. A YouTube channel URL is required only when syncing or monitoring the channel.

## Frontend

```powershell
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/frontend
npm install
$env:VITE_API_TARGET="http://127.0.0.1:8001"
npm run dev -- --host 127.0.0.1 --port 5173
```

The frontend runs on `http://127.0.0.1:5173` and proxies `/api` to `VITE_API_TARGET`.

## Local Security Boundary

This is a local personal workspace. The backend has no authentication layer, and the LLM API key is stored in local runtime settings. Keep the backend bound to `127.0.0.1` and do not expose the API port to a LAN or public network.

The backend rejects non-local `Host` headers by default as an extra guard. To intentionally run behind your own trusted access control, set `YCA_ALLOW_REMOTE_ACCESS=true`.

## Current Features

- Configure one YouTube channel from the Settings page.
- Save LLM and browser settings first, then add the channel URL when you are ready to sync or monitor.
- Choose browser collection engine: Playwright, DrissionPage, or CDP for an existing local browser.
- Sync recent videos from the configured channel.
- Analyze a selected video with real metadata, transcript/subtitle collection, comments stub, channel profile, metrics, and LLM-first report generation.
- Show raw script and cached Chinese translation on the Video Report page.
- Re-run the latest report with LLM from the page.
- Force retranslate the latest transcript with the configured OpenAI-compatible LLM endpoint.
- Show only successful LLM report idea cards by default in the Idea Lab.
- Clean old rule-generated idea cards from local runtime storage.
- Keep comment collection as a first-class reserved interface returning `not_configured`.

## LLM Configuration

The Settings page can save:

- `LLM Base URL`
- `LLM Analysis Model`
- `LLM Translation Model`
- `LLM API Key`

The API key is stored locally in `backend/.runtime/workspace-settings.json`, but `/api/settings` never returns the key to the browser. It only returns `openai_api_key_set`.

Environment fallback variables are also supported:

- `YCA_OPENAI_BASE_URL`
- `YCA_OPENAI_ANALYSIS_MODEL`
- `YCA_OPENAI_TRANSLATION_MODEL`
- `YCA_OPENAI_API_KEY`

## Verification

```powershell
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/backend
python -m pytest -q

cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/frontend
npm run build
```

Avoid repeatedly testing YouTube collection against many videos in a short time; use one-off manual checks to reduce YouTube rate-limit risk.
