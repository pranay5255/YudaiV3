#!/usr/bin/env python3
"""Sandbox session server entrypoint for realtime Phase 1."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os

import httpx
import uvicorn

from config.realtime_flags import get_realtime_feature_flags
from db.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from realtime.sandbox_routes import router as sandbox_router
from realtime.solve_routes import router as solve_router


async def _heartbeat_loop() -> None:
    controller_base_url = os.getenv("CONTROLLER_BASE_URL", "").rstrip("/")
    sandbox_id = os.getenv("SANDBOX_ID")
    heartbeat_secret = os.getenv("CONTROLLER_HEARTBEAT_SECRET")
    interval_seconds = int(os.getenv("SANDBOX_HEARTBEAT_INTERVAL_SECONDS", "10"))

    if not controller_base_url or not sandbox_id:
        return

    heartbeat_url = (
        f"{controller_base_url}/controller/sandboxes/{sandbox_id}/heartbeat"
    )

    headers = {}
    if heartbeat_secret:
        headers["X-Controller-Heartbeat-Secret"] = heartbeat_secret

    while True:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(heartbeat_url, headers=headers)
        except Exception as exc:  # pragma: no cover - defensive logging path
            print(f"[sandbox] heartbeat failed: {exc}")

        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[sandbox] starting sandbox session server")
    init_db()

    heartbeat_task = asyncio.create_task(_heartbeat_loop(), name="sandbox-heartbeat")

    yield

    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass

    print("[sandbox] shutting down")


app = FastAPI(
    title="Yudai Sandbox Session Server",
    description="Internal sandbox server for controller-brokered execution",
    version="3.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("SANDBOX_ALLOW_ORIGINS", "https://yudai.app").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sandbox_router)
app.include_router(solve_router)


@app.get("/")
def root():
    return {
        "service": "yudai-sandbox-session-server",
        "phase": "phase1",
        "docs": "/docs",
    }


@app.get("/realtime/flags")
def realtime_flags():
    flags = get_realtime_feature_flags()
    return {"flags": flags.as_dict()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8100")))
