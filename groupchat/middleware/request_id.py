"""Request ID tracking middleware"""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add unique request IDs for tracking and correlation"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add unique request ID to request state and response headers"""
        request_id = str(uuid.uuid4())
        
        # Add request ID to request state for use in handlers and logs
        request.state.request_id = request_id
        
        # Process request
        response: Response = await call_next(request)
        
        # Add request ID to response headers for client tracking
        response.headers["X-Request-ID"] = request_id
        
        return response