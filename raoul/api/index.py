"""
api/index.py — Raoul backend as a Vercel serverless function.

Vercel routes all /api/* requests here via vercel.json rewrite.
For local development: uvicorn api.index:app --reload --port 8000
"""

import json
import os
from typing import List, Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Import from underscore-prefixed helper modules (Vercel ignores these as endpoints)
from api._prompts import SYSTEM_PROMPT
from api._tools import TOOL_DEFINITIONS, execute_tool

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

MODEL = os.getenv("MODEL", "claude-sonnet-4-6")
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 5

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────

app = FastAPI(title="Raoul — NYC Rules Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ─────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    language: Optional[str] = "English"
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str
    tool_calls_made: List[str] = []
    model: str


# ─────────────────────────────────────────────
# Core agentic loop
# ─────────────────────────────────────────────

def build_system_prompt(language: str) -> str:
    system = SYSTEM_PROMPT
    if language and language.lower() not in ("english", "en"):
        system += (
            f"\n\n## LANGUAGE INSTRUCTION\n"
            f"The user has selected **{language}** as their preferred language. "
            f"Respond entirely in {language}, including all citations and disclaimers. "
            f"Maintain the same level of specificity and accuracy in {language} as you would in English."
        )
    return system


def run_agentic_loop(messages: list, system: str) -> tuple[str, list]:
    tool_calls_made = []
    current_messages = messages.copy()

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=current_messages,
            tools=TOOL_DEFINITIONS,
        )

        if response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            tool_results = []

            for block in tool_use_blocks:
                tool_calls_made.append(block.name)
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })

            current_messages.append({
                "role": "assistant",
                "content": [b.model_dump() for b in response.content],
            })
            current_messages.append({
                "role": "user",
                "content": tool_results,
            })
        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            return final_text.strip(), tool_calls_made

    return (
        "I ran into an issue gathering all the information I needed. "
        "Please try your question again, or call 311 for direct assistance.",
        tool_calls_made,
    )


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    messages = []
    for m in request.messages:
        if m.role not in ("user", "assistant"):
            raise HTTPException(status_code=400, detail=f"Invalid role: {m.role}")
        messages.append({"role": m.role, "content": m.content})

    system = build_system_prompt(request.language or "English")

    response_text, tools_used = run_agentic_loop(messages, system)
    return ChatResponse(
        response=response_text,
        tool_calls_made=tools_used,
        model=MODEL,
    )


@app.exception_handler(anthropic.APIError)
async def anthropic_error_handler(request: Request, exc: anthropic.APIError):
    return JSONResponse(
        status_code=502,
        content={"error": "AI service error. Please try again.", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Something went wrong. Please try again."},
    )
