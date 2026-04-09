"""
main.py — Raoul NYC Rules Assistant backend
FastAPI server with Claude-powered agentic loop and NYC Open Data tools.

Run locally:
    uvicorn main:app --reload --port 8000

Environment variables (see .env.example):
    ANTHROPIC_API_KEY  — required
    ALLOWED_ORIGINS    — comma-separated CORS origins (default: *)
    MODEL              — Claude model name (default: claude-sonnet-4-6)
"""

import json
import os
import time
from typing import List, Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from prompts import SYSTEM_PROMPT
from tools import TOOL_DEFINITIONS, execute_tool

load_dotenv()

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

MODEL = os.getenv("MODEL", "claude-sonnet-4-6")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 5  # safety limit on agentic loop iterations

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────

app = FastAPI(
    title="Raoul — NYC Rules Assistant",
    description="Plain-language answers to NYC rules and regulations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ─────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
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
    """Inject language preference into the system prompt."""
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
    """
    Run the Claude agentic loop with tool use.
    Returns (final_text_response, list_of_tool_names_called).
    """
    tool_calls_made = []
    current_messages = messages.copy()

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=current_messages,
            tools=TOOL_DEFINITIONS,
        )

        if response.stop_reason == "tool_use":
            # Collect tool uses from this response
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

            # Append assistant turn (with tool use) and tool results
            current_messages.append({
                "role": "assistant",
                "content": [b.model_dump() for b in response.content],
            })
            current_messages.append({
                "role": "user",
                "content": tool_results,
            })

        else:
            # Terminal response — extract text
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            return final_text.strip(), tool_calls_made

    # Safety fallback if we somehow exhaust tool rounds
    return (
        "I ran into an issue gathering all the information I needed. "
        "Please try your question again, or call 311 for direct assistance.",
        tool_calls_made,
    )


def stream_agentic_loop(messages: list, system: str):
    """
    Streaming variant: yields SSE-formatted chunks.
    Tool calls happen synchronously before streaming the final response.
    """
    # First, run all tool calls non-streaming
    tool_calls_made = []
    current_messages = messages.copy()

    for _ in range(MAX_TOOL_ROUNDS):
        # Peek at stop_reason with a non-streaming call to handle tools
        peek = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=current_messages,
            tools=TOOL_DEFINITIONS,
        )

        if peek.stop_reason == "tool_use":
            tool_use_blocks = [b for b in peek.content if b.type == "tool_use"]
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
                "content": [b.model_dump() for b in peek.content],
            })
            current_messages.append({"role": "user", "content": tool_results})

            # Notify frontend that a tool was called
            for name in tool_calls_made[-len(tool_use_blocks):]:
                yield f"data: {json.dumps({'tool': name})}\n\n"
        else:
            break

    # Now stream the final response
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=current_messages,
    ) as stream:
        for text_chunk in stream.text_stream:
            yield f"data: {json.dumps({'text': text_chunk})}\n\n"

    yield f"data: {json.dumps({'done': True, 'tools': tool_calls_made})}\n\n"


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "Raoul — NYC Rules Assistant",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Accepts conversation history and returns Raoul's response.

    Set stream=true in the request body to receive a Server-Sent Events stream.
    Each SSE event is a JSON object with one of:
      { "text": "..." }        — a text chunk
      { "tool": "tool_name" }  — a tool was called (informational)
      { "done": true, "tools": [...] } — stream complete
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    # Build message list in Anthropic format
    messages = []
    for m in request.messages:
        if m.role not in ("user", "assistant"):
            raise HTTPException(status_code=400, detail=f"Invalid role: {m.role}")
        messages.append({"role": m.role, "content": m.content})

    system = build_system_prompt(request.language or "English")

    if request.stream:
        return StreamingResponse(
            stream_agentic_loop(messages, system),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming (default)
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
