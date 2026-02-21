#!/usr/bin/env python3
"""Controller host entrypoint for realtime Phase 1."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import uvicorn

from auth import auth_router
from config.realtime_flags import get_realtime_feature_flags
from daifuUserAgent.session_routes import router as session_router
from db.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from github import github_router
from realtime.controller_routes import router as controller_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[controller] starting realtime controller host")
    init_db()
    yield
    print("[controller] shutting down")


app = FastAPI(
    title="Yudai Realtime Controller",
    description="Phase 1 controller host for sandbox lifecycle + metadata persistence",
    version="3.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "ALLOW_ORIGINS", "http://localhost:3000,https://yudai.app"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing APIs
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(github_router, prefix="/github", tags=["github"])
app.include_router(session_router, prefix="/daifu", tags=["sessions"])

# New Phase 1 controller lifecycle APIs
app.include_router(controller_router)


@app.get("/")
def root():
    return {
        "service": "yudai-controller",
        "phase": "phase1",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "yudai-controller"}


@app.get("/realtime/flags")
def realtime_flags():
    flags = get_realtime_feature_flags()
    return {"flags": flags.as_dict()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
