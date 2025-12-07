from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-XSS-Protection"] = "1; mode=block"

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["X-Content-Type-Options"] = "nosniff"

        return response