"""FastAPI router for interacting with the DAifu agent."""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException
import openai

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
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:  # pragma: no cover - network failures
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    history.append(("DAifu", reply))
    return {"reply": reply, "conversation": history}
