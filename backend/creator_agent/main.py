from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from creator_agent.api import router
from creator_agent.config import Settings
from creator_agent.security import LocalOnlyMiddleware


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(LocalOnlyMiddleware, allow_remote_access=settings.allow_remote_access)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("YCA_API_PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port)
