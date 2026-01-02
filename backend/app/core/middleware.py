"""Custom middleware for the application."""
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Use root logger to ensure logs appear
logger = logging.getLogger("app.middleware")
logger.setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses.

    Logs:
    - Request method, path, and headers
    - Response status code and timing
    - Unique request ID for tracing
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Store request ID for use in logs
        request.state.request_id = request_id

        # Record start time
        start_time = time.perf_counter()

        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        # Log request
        logger.info(
            f"[{request_id}] {method} {path}"
            + (f"?{query}" if query else "")
            + f" - Client: {client_ip}"
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log response
            logger.info(
                f"[{request_id}] {method} {path} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration_ms:.2f}ms"
            )

            # Add request ID to response headers for tracing
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log error
            logger.error(
                f"[{request_id}] {method} {path} - "
                f"Error: {type(e).__name__}: {str(e)} - "
                f"Duration: {duration_ms:.2f}ms"
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
