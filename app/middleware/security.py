import secrets
import hashlib
import hmac
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=(), interest-cohort=()"
        )
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )

        return response


CSRF_COOKIE_NAME = "_predicate_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_EXPIRY = 3600
CSRF_SIGNED_PATHS = {"/api/v1/query/compile", "/api/v1/export/async"}


def _sign_token(token: str, secret: str) -> str:
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def _generate_csrf_token(secret: str) -> tuple[str, str]:
    token = secrets.token_hex(32)
    timestamp = str(int(time.time()))
    signed = _sign_token(f"{token}:{timestamp}", secret)
    return f"{token}:{timestamp}:{signed}", token


def _validate_csrf_token(token_value: str, secret: str) -> bool:
    parts = token_value.split(":")
    if len(parts) != 3:
        return False
    raw_token, timestamp_str, provided_sig = parts
    try:
        ts = int(timestamp_str)
    except ValueError:
        return False
    if time.time() - ts > CSRF_TOKEN_EXPIRY:
        return False
    expected_sig = _sign_token(f"{raw_token}:{timestamp_str}", secret)
    return hmac.compare_digest(provided_sig, expected_sig)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str = None):
        super().__init__(app)
        self.secret_key = secret_key or secrets.token_hex(32)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith("/health") or request.url.path.startswith("/ready") or request.url.path == "/metrics":
            return await call_next(request)

        if request.method in ("GET", "HEAD", "OPTIONS"):
            if request.method == "GET" and request.url.path == "/":
                response = await call_next(request)
                token_value, raw_token = _generate_csrf_token(self.secret_key)
                response.set_cookie(
                    CSRF_COOKIE_NAME,
                    token_value,
                    httponly=False,
                    secure=True,
                    samesite="strict",
                    max_age=CSRF_TOKEN_EXPIRY,
                )
                return response
            return await call_next(request)

        if request.url.path in CSRF_SIGNED_PATHS:
            cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
            if cookie_token:
                header_token = request.headers.get(CSRF_HEADER_NAME)

                if not header_token:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF token missing."},
                    )

                if not _validate_csrf_token(cookie_token, self.secret_key):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF token expired or invalid."},
                    )

                if not hmac.compare_digest(cookie_token, header_token):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF token mismatch."},
                    )

        return await call_next(request)
