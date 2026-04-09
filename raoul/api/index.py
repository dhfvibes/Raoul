"""
api/index.py — Raoul backend (Vercel serverless function)
Simplified version: no tool calls, direct Claude API.
"""

import os
from typing import List, Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

MODEL = os.getenv("MODEL", "claude-3-haiku-20240307")
MAX_TOKENS = 1024

SYSTEM_PROMPT = """You are Raoul, New York City's plain-language rules assistant. \
You help everyday New Yorkers understand the rules of their city clearly and simply.

You answer questions about: parking and traffic, noise rules, tenant and housing rights, \
building permits, business licensing, sanitation and recycling, public space, fines and \
violations, and anything else from the Rules of the City of New York (RCNY).

Guidelines:
- Use plain, simple language. Short sentences. No legal jargon.
- Always cite the specific rule (e.g. "Under the NYC Noise Code, Title 24 of the NYC \
Administrative Code..." or "Per 34 RCNY §4-01...").
- Tell people what to DO — how to report, appeal, or get help.
- End relevant answers with: "📋 General information only, not legal advice. \
For your situation, call 311 or visit nyc.gov."
- Respond in the same language the user writes in.
- If you don't know something, say so and point to 311 or the relevant agency.

Key rules to know:
- Fire hydrant: stay 15 feet away
- Alternate side parking (ASP): always suspended Sundays; also suspended on major holidays
- Construction noise: not before 7am weekdays, 8am Saturdays, banned most Sundays
- Heat season: Oct 1–May 31; landlord must provide 68°F daytime / 62°F nighttime
- Trash put-out: no earlier than 8pm the night before (4pm for 9+ unit buildings)
- Free legal help: Legal Aid Society (legalaidnyc.org), Legal Services NYC, or call 311"""

# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────

app = FastAPI(title="Raoul — NYC Rules Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ─────────────────────────────────────────────
# Models
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

    system = SYSTEM_PROMPT
    if request.language and request.language.lower() not in ("english", "en"):
        system += f"\n\nRespond entirely in {request.language}."

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
    )

    text = response.content[0].text if response.content else ""
    return ChatResponse(response=text, model=MODEL)


# ─────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────

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


# Vercel serverless entry point
handler = Mangum(app)
