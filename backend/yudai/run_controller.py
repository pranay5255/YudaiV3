#!/usr/bin/env python3
"""Controller host entrypoint for realtime Phase 1."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import uvicorn

from yudai.auth import auth_router
from yudai.config.realtime_flags import get_realtime_feature_flags
from yudai.daifuUserAgent.session_routes import router as session_router
from yudai.db.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from yudai.github import github_router
from yudai.realtime.controller_routes import router as controller_router
from yudai.test_routes import router as test_router, test_api_enabled
from yudai.types import HealthResponse, RealtimeFlagsResponse, RootResponse


def _parse_allow_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[controller] starting realtime controller host")
    init_db()
    yield
    print("[controller] shutting down")


fastapi_app = FastAPI(
    title="Yudai Realtime Controller",
    description="Phase 1 controller host for sandbox lifecycle + metadata persistence",
    version="3.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

# Canonical API mounts only.
fastapi_app.include_router(auth_router, prefix="/auth", tags=["auth"])
fastapi_app.include_router(github_router, prefix="/github", tags=["github"])
fastapi_app.include_router(session_router, prefix="/daifu", tags=["sessions"])
fastapi_app.include_router(controller_router)
if test_api_enabled():
    fastapi_app.include_router(test_router)


@fastapi_app.get("/", response_model=RootResponse)
def root():
    return {
        "service": "yudai-controller",
        "phase": "phase1",
        "docs": "/docs",
    }


@fastapi_app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "healthy", "service": "yudai-controller"}


@fastapi_app.get("/realtime/flags", response_model=RealtimeFlagsResponse)
def realtime_flags():
    flags = get_realtime_feature_flags()
    return {"flags": flags.as_dict()}


# Wrap the full ASGI app so CORS headers are still added when FastAPI converts
# unhandled exceptions into a 500 response.
app = CORSMiddleware(
    app=fastapi_app,
    allow_origins=_parse_allow_origins(
        os.getenv(
            "ALLOW_ORIGINS",
            "http://localhost:3000,https://yudai.app,https://www.yudai.app",
        )
    ),
    allow_origin_regex=os.getenv("ALLOW_ORIGIN_REGEX"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
