"""Main FastAPI application for GroupChat"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from groupchat.api import admin, agent, contacts, demo, expert_preferences, health, ledger, matching, payments, queries, webhooks, websockets
from groupchat.config import settings
from groupchat.db.database import close_db, init_db
from groupchat.middleware.request_id import RequestIDMiddleware
from groupchat.middleware.rate_limit import RateLimitMiddleware
from groupchat.middleware.logging import LoggingMiddleware
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
    description="""
    ## Network Intelligence System with Micropayments

    GroupChat routes questions to relevant experts in your network, synthesizes answers with citations, 
    and distributes micropayments to contributors.

    ### Key Features
    - 🎯 **Smart Expert Matching**: AI-powered routing based on expertise and trust metrics
    - 💬 **Multi-Channel Communication**: SMS, WhatsApp, email integration via Twilio  
    - 📝 **Citation by Design**: Every claim traces back to the contributor
    - 💰 **Micropayments**: Automatic payment distribution (70% contributors, 20% platform, 10% referrers)
    - 🔍 **Knowledge Graph**: Build networks of who knows what
    - 🤖 **Agent Tools**: LangGraph integration for workflow automation

    ### Workflow
    1. **Submit Query** → Question analyzed and matched to experts
    2. **Expert Outreach** → Relevant contacts receive SMS/notifications  
    3. **Collect Responses** → Gather contributions from network
    4. **Synthesize Answer** → AI combines responses with citations
    5. **Distribute Payment** → Micropayments sent to contributors

    ### Quick Start
    ```bash
    # Submit a query
    POST /api/v1/queries
    {
      "user_phone": "+1234567890",
      "question_text": "What are the latest AI trends?",
      "max_spend_cents": 500
    }
    
    # Check status
    GET /api/v1/queries/{query_id}/status
    
    # Get final answer with citations
    GET /api/v1/queries/{query_id}/answer
    ```
    """,
    version="0.1.0-mvp",
    contact={
        "name": "GroupChat Team",
        "url": "https://github.com/brianellis1997/ErrandBoy",
    },
    license_info={
        "name": "MIT",
        "url": "https://github.com/brianellis1997/ErrandBoy/blob/main/LICENSE",
    },
    lifespan=lifespan,
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
)

# Configure middleware (order matters - last added runs first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,
    requests_per_hour=1000,
    enable_rate_limiting=settings.app_env != "development",
)
app.add_middleware(RequestIDMiddleware)


# Root endpoint - serve frontend
@app.get("/")
async def root():
    """Root endpoint - serve main interface"""
    from fastapi.responses import FileResponse
    import os
    
    # Check if index.html exists
    static_path = os.path.join("static", "index.html")
    if os.path.exists(static_path):
        return FileResponse(static_path)
    else:
        # Fallback to redirect to static file
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/index.html")


# API status endpoint
@app.get("/status", response_class=JSONResponse)
async def api_status() -> dict[str, Any]:
    """API status endpoint for programmatic access"""
    return {
        "name": "GroupChat API",
        "version": "0.1.0",
        "status": "operational",
        "frontend": "/",
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
    matching.router,
    prefix="/api/v1/matching",
    tags=["matching"]
)
app.include_router(
    webhooks.router,
    prefix="/api/v1/webhooks",
    tags=["webhooks"]
)
app.include_router(
    admin.router,
    prefix="/api/v1/admin",
    tags=["admin"]
)
app.include_router(
    ledger.router,
    prefix="/api/v1/ledger",
    tags=["ledger"]
)
app.include_router(
    payments.router,
    prefix="/api/v1/payments",
    tags=["payments"]
)
app.include_router(
    agent.router,
    prefix="/api/v1/agent",
    tags=["agent"]
)
app.include_router(
    websockets.router,
    prefix="/api/v1/ws",
    tags=["websockets"]
)
app.include_router(
    demo.router,
    prefix="/api/v1/demo",
    tags=["demo"]
)
app.include_router(
    expert_preferences.router,
    tags=["expert-preferences"]
)

# Answer display route
@app.get("/answer/{query_id}")
async def answer_page(query_id: str):
    """Serve answer display page with query ID"""
    from fastapi.responses import FileResponse
    import os
    
    # Check if answer.html exists
    static_path = os.path.join("static", "answer.html")
    if os.path.exists(static_path):
        response = FileResponse(static_path)
        # Add query_id to the response for JavaScript to pick up
        response.headers["X-Query-ID"] = query_id
        return response
    else:
        # Fallback to redirect to static file with query parameter
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/static/answer.html?query_id={query_id}")


# Expert interface route
@app.get("/expert")
async def expert_interface():
    """Serve expert response interface"""
    from fastapi.responses import FileResponse
    import os
    
    # Check if expert.html exists
    static_path = os.path.join("static", "expert.html")
    if os.path.exists(static_path):
        return FileResponse(static_path)
    else:
        # Fallback to redirect to static file
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/expert.html")


# Enhanced expert interface route
@app.get("/expert/enhanced")
async def enhanced_expert_interface():
    """Serve enhanced expert response interface with real-time notifications"""
    from fastapi.responses import FileResponse
    import os
    
    # Serve the enhanced expert interface
    static_path = os.path.join("static", "expert-enhanced.html")
    if os.path.exists(static_path):
        return FileResponse(static_path)
    else:
        # Fallback to redirect to static file
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/expert-enhanced.html")


# Admin dashboard route
@app.get("/admin")
async def admin_dashboard():
    """Serve admin dashboard interface"""
    from fastapi.responses import FileResponse
    import os
    
    # Check if admin.html exists
    static_path = os.path.join("static", "admin.html")
    if os.path.exists(static_path):
        return FileResponse(static_path)
    else:
        # Fallback to redirect to static file
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/admin.html")


# Demo control panel route
@app.get("/demo")
async def demo_control_panel():
    """Serve demo control panel interface"""
    from fastapi.responses import FileResponse
    import os
    
    # Check if demo.html exists
    static_path = os.path.join("static", "demo.html")
    if os.path.exists(static_path):
        return FileResponse(static_path)
    else:
        # Fallback to redirect to static file
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/demo.html")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


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
