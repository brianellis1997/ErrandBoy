"""Request/response logging middleware"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses"""

    def __init__(self, app, log_requests: bool = True, log_responses: bool = True):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details"""
        start_time = time.time()
        
        # Get request ID if available
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log request
        if self.log_requests:
            self._log_request(request, request_id)
        
        # Process request
        response: Response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        if self.log_responses:
            self._log_response(request, response, process_time, request_id)
        
        # Add timing header
        response.headers["X-Process-Time"] = str(round(process_time, 4))
        
        return response

    def _log_request(self, request: Request, request_id: str) -> None:
        """Log incoming request details"""
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        logger.info(
            "Incoming request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": client_host,
                "user_agent": user_agent,
                "content_type": request.headers.get("content-type"),
                "content_length": request.headers.get("content-length"),
            },
        )

    def _log_response(
        self,
        request: Request,
        response: Response,
        process_time: float,
        request_id: str,
    ) -> None:
        """Log response details"""
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": round(process_time, 4),
                "response_size": response.headers.get("content-length"),
                "content_type": response.headers.get("content-type"),
            },
        )
        
        # Log slow requests as warnings
        if process_time > 5.0:  # 5 seconds
            logger.warning(
                "Slow request detected",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "process_time": round(process_time, 4),
                    "status_code": response.status_code,
                },
            )