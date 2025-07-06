from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import subprocess
import os
from .models import RunCLIRequest, RunCLIResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLI_PATH = os.path.join(BASE_DIR, '..', 'YudaiCLI', 'codex-cli', 'bin', 'codex.js')

async def _run_cli(args: list[str]) -> RunCLIResponse:
    proc = await run_in_threadpool(
        subprocess.Popen,
        ['node', CLI_PATH, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ
    )
    stdout, stderr = await run_in_threadpool(proc.communicate)
    return RunCLIResponse(stdout=stdout.decode(), stderr=stderr.decode())

@app.post('/api/run-cli', response_model=RunCLIResponse)
async def run_cli(req: RunCLIRequest):
    return await _run_cli(req.args)
