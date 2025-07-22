from fastapi import FastAPI
from backend.repo_processorGitIngest.filedeps import router

app = FastAPI()
app.include_router(router)
