# YouTube Creator Growth Agent

MVP app for monitoring and analyzing YouTube creator, marketing, and entrepreneurship channels.

The app is isolated from Hermes core. It uses a FastAPI backend, MySQL-ready SQLAlchemy models, Redis/RQ-style jobs, and a React/Vite frontend.

## Backend

```powershell
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/backend
python -m pip install -e ".[dev]"
python -m pytest -v
uvicorn creator_agent.main:app --reload
```

The backend defaults to:
- MySQL: `mysql+pymysql://creator_agent:creator_agent@localhost:3306/creator_agent`
- Redis: `redis://localhost:6379/0`

Override these with:
- `YCA_DATABASE_URL`
- `YCA_REDIS_URL`

## Frontend

```powershell
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/frontend
npm install
npm run dev
```

The frontend runs on `http://127.0.0.1:5173` and proxies `/api` to `http://127.0.0.1:8000`.

## MVP Notes

- Comment collection is a first-class interface and returns `not_configured` until a collector is connected.
- YouTube metadata and transcript tools are deterministic local stubs in the first implementation.
- The job pipeline is designed for Redis/RQ, while direct service tests run without Redis.
- `POST /api/analysis/video` is currently an API shell and returns `mock_queued` until it is wired to the real job queue.
