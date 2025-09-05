"""Main FastAPI application for GroupChat"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from groupchat.api import contacts, health, queries, webhooks
from groupchat.config import settings
from groupchat.db.database import close_db, init_db
from groupchat.utils.logging import setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    logger.info("Starting GroupChat application...")

    # Initialize database connection
    await init_db()

    # Add any other startup tasks here
    logger.info("Application startup complete")

    yield

    # Cleanup
    logger.info("Shutting down GroupChat application...")
    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="GroupChat API",
    description="Network Intelligence System with Micropayments",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/", response_class=JSONResponse)
async def root() -> dict[str, Any]:
    """Root endpoint"""
    return {
        "name": "GroupChat API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs" if settings.app_debug else None,
    }


# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(
    contacts.router,
    prefix="/api/v1/contacts",
    tags=["contacts"]
)
app.include_router(
    queries.router,
    prefix="/api/v1/queries",
    tags=["queries"]
)
app.include_router(
    webhooks.router,
    prefix="/api/v1/webhooks",
    tags=["webhooks"]
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.app_debug else "An error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "groupchat.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )
