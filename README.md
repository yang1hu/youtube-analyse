# YouTube Creator Growth Agent

MVP app for monitoring and analyzing YouTube creator, marketing, and entrepreneurship channels.

The app is isolated from Hermes core. This scaffold starts the backend package and configuration for a planned FastAPI app with MySQL-ready SQLAlchemy models, Redis/RQ jobs, and a React/Vite frontend.

Run:
cd C:/Users/Admin/Desktop/git_project/youtube-creator-agent/backend
python -m pytest tests/test_models.py::test_settings_defaults_are_mysql_and_redis_ready -v
Expected PASS. If dependencies are missing, install backend package in editable dev mode with:
python -m pip install -e ".[dev]"
Then rerun the test.
