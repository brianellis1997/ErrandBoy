#!/usr/bin/env python
"""Start script for Railway deployment"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "groupchat.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )