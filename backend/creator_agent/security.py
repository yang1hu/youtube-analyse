from __future__ import annotations

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "testclient", "testserver"}


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, allow_remote_access: bool = False) -> None:
        super().__init__(app)
        self.allow_remote_access = allow_remote_access

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.allow_remote_access:
            return await call_next(request)

        host_header = request.headers.get("host") or ""
        parsed = urlsplit(f"//{host_header}")
        normalized_host = (parsed.hostname or host_header).strip().lower()

        if normalized_host in LOCAL_HOSTS:
            return await call_next(request)

        client_host = (request.client.host if request.client else "").strip().lower()
        if not normalized_host and client_host in LOCAL_HOSTS:
            return await call_next(request)

        return JSONResponse(
            status_code=403,
            content={"detail": "Remote access is disabled. Bind and browse this local workspace through 127.0.0.1."},
        )
