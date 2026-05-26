"""
TrialMind Agent Service — FastAPI
Manages conversations and streams agent responses.
"""
import sys
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from agent import run_agent
from config import settings

app = FastAPI(
    title="TrialMind Agent Service",
    description="Conversational AI agent for clinical trial analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(settings.database_url)


# ─── Request/Response models ──────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: Message
    charts: list[dict] = []
    tool_calls: list[dict] = []


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Send a message to the agent. Creates a new conversation if conversation_id is None.
    The agent has full history of the conversation.
    """
    conv_id = req.conversation_id or str(uuid.uuid4())

    # Load existing conversation history
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT messages FROM conversations WHERE id = :id"),
            {"id": conv_id},
        ).fetchone()

    if existing:
        import json
        history: list[dict] = json.loads(existing[0]) if isinstance(existing[0], str) else (existing[0] or [])
    else:
        history = []

    # Append new user message
    history.append({"role": "user", "content": req.message})

    # Run the agent
    result = await run_agent(history, conversation_id=conv_id)

    # Append assistant reply
    history.append({"role": "assistant", "content": result["content"]})

    # Persist conversation
    title = history[0]["content"][:60] + "..." if len(history[0]["content"]) > 60 else history[0]["content"]
    import json as json_mod
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO conversations (id, title, messages, updated_at)
                VALUES (:id, :title, CAST(:messages AS JSONB), NOW())
                ON CONFLICT (id) DO UPDATE
                SET messages = CAST(:messages AS JSONB), updated_at = NOW()
            """),
            {
                "id": conv_id,
                "title": title,
                "messages": json_mod.dumps(history),
            },
        )
        conn.commit()

    return ChatResponse(
        conversation_id=conv_id,
        message=Message(role="assistant", content=result["content"]),
        charts=result.get("charts", []),
        tool_calls=result.get("tool_calls", []),
    )


@app.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(limit: int = 20, offset: int = 0):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, title, created_at, updated_at,
                       jsonb_array_length(messages) as message_count
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        ).mappings().fetchall()
    return [
        ConversationSummary(
            id=r["id"],
            title=r["title"] or "Untitled",
            created_at=str(r["created_at"]),
            updated_at=str(r["updated_at"]),
            message_count=r["message_count"] or 0,
        )
        for r in rows
    ]


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM conversations WHERE id = :id"),
            {"id": conversation_id},
        ).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return dict(row)


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM conversations WHERE id = :id"), {"id": conversation_id})
        conn.commit()
    return {"deleted": True}


@app.get("/suggested-queries")
def suggested_queries():
    """Return example queries to help users get started."""
    return {
        "queries": [
            "What is the overall success rate of Phase 3 clinical trials?",
            "Show me a chart of success rates by therapeutic area",
            "Compare industry-sponsored vs NIH-sponsored trial success rates",
            "What are the top 10 sponsors by number of completed trials?",
            "How does enrollment size affect trial success?",
            "Predict the success probability for a Phase 3 oncology drug trial with 500 patients",
            "Show trial volume over time as a chart",
            "What factors most commonly lead to trial failure?",
            "How accurate is the prediction model on historical data?",
            "Show me recent terminated oncology trials and why they might have failed",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
