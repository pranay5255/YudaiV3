"""FastAPI router for interacting with the DAifu agent."""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException
import requests

from models import ChatRequest
from .prompt import build_daifu_prompt

router = APIRouter()

# Simple in-memory conversation store
_conversations: Dict[str, List[Tuple[str, str]]] = {}

# Basic repository context fed to the prompt
GITHUB_CONTEXT = (
    "Repository root: YudaiV3\n"
    "Key frontend file: src/components/Chat.tsx\n"
    "Key frontend file: src/App.tsx\n"
    "Backend FastAPI: backend/repo_processor/filedeps.py"
)


def _get_history(conv_id: str) -> List[Tuple[str, str]]:
    return _conversations.setdefault(conv_id, [])


@router.post("/chat/daifu")
async def chat_daifu(request: ChatRequest):
    """Process a chat message via the DAifu agent."""
    conv_id = request.conversation_id or "default"
    history = _get_history(conv_id)
    history.append(("User", request.message.content))

    prompt = build_daifu_prompt(GITHUB_CONTEXT, history)

    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
        }

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # pragma: no cover - network failures
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    history.append(("DAifu", reply))
    return {"reply": reply, "conversation": history}
