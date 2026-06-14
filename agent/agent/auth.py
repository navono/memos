import warnings

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from agent.config import settings


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": detail})


def verify_token(token: str) -> dict | JSONResponse:
    """Verify a Memos JWT and return the claims, or an error response."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            payload = jwt.decode(
            token,
            settings.memos_secret.encode(),
            algorithms=["HS256"],
            options={
                "require": ["iss", "sub", "aud"],
                "verify_iss": True,
                "verify_aud": True,
            },
            issuer="memos",
            audience="user.access-token",
        )
    except jwt.ExpiredSignatureError:
        return _unauthorized("Token expired")
    except jwt.InvalidTokenError as e:
        return _unauthorized(f"Invalid token: {e}")

    try:
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        return _unauthorized("Invalid token subject")

    return {"user_id": user_id, "username": payload.get("name", "")}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/v1/healthz":
            return await call_next(request)

        # Trust X-User-Id from the Go proxy (already authenticated).
        # The Go proxy verifies the JWT and injects X-User-Id and X-User-Name.
        user_id = request.headers.get("X-User-Id", "")
        if user_id:
            try:
                request.state.user_id = int(user_id)
            except ValueError:
                return _unauthorized("Invalid X-User-Id")
            request.state.auth_token = request.headers.get("X-Auth-Token", "")
            request.state.username = request.headers.get("X-User-Name", "")
            return await call_next(request)

        # Fallback: verify JWT directly (for direct agent access).
        token = request.headers.get("X-Auth-Token", "")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return _unauthorized("Missing authentication token")

        claims = verify_token(token)
        if isinstance(claims, JSONResponse):
            return claims

        request.state.user_id = claims["user_id"]
        request.state.auth_token = token
        request.state.username = claims.get("username", "")

        return await call_next(request)
