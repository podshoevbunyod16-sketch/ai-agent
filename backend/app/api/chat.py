"""
POST /api/chat — Main chat endpoint with SSE streaming.
Protected by Firebase auth. Implements agent loop with tool calling.

Agent loop:
  1. Gather tools from active MCP servers
  2. Stream LLM response
  3. If tool_calls → execute via MCP → repeat (max 10 iterations)
  4. Stream final content to client

SSE format per line:
  data: {"type":"content","content":"hello"}
  data: {"type":"tool_calls","tool_calls":[...]}
  data: {"type":"tool_result","tool_name":"...","result":"..."}
  data: {"type":"finish","reason":"stop","usage":{...}}
  data: {"type":"done"}
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Conversation, Message, Memory, MCPServer, User
from app.services.llm_client import get_llm_client, LLMClientError
from app.services.web_search import tavily_search
from app.mcp.mcp_client_manager import (
    active_mcp_tools_for_user,
    execute_mcp_tool,
)
from app.utils.firebase_auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])

# --- Helper: parse <thinking> blocks ---
def parse_chain_of_thought(content: str) -> tuple:
    """Extract <thinking>...</thinking> blocks and return (clean_content, thought)."""
    pattern = r"<thinking>(.*?)</thinking>"
    thoughts = re.findall(pattern, content, re.DOTALL)
    clean = re.sub(pattern, "", content, flags=re.DOTALL).strip()
    return clean, "\n".join(thoughts) if thoughts else None


# --- Helper: build system prompt with memories ---
async def build_system_prompt(db: AsyncSession, user: User) -> str:
    parts = [
        "You are a helpful AI assistant. You can use tools to help the user.",
        "Available tools: web_search (search the internet), save_memory (save facts about the user).",
        "MCP tools may also be available — use them when relevant.",
        "Think step by step. Wrap your reasoning in <thinking>...</thinking> tags.",
        "Always respond in the same language as the user's message.",
    ]
    # Inject memories
    result = await db.execute(
        select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at.desc()).limit(20)
    )
    memories = result.scalars().all()
    if memories:
        parts.append("\nFacts you know about the user:")
        for m in memories:
            parts.append(f"- {m.content}")
    return "\n".join(parts)


# --- Helper: save memory from tool call ---
async def save_user_memory(db: AsyncSession, user_id: int, content: str) -> str:
    mem = Memory(
        user_id=user_id,
        content=content,
        importance=1.0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(mem)
    await db.commit()
    return f"Memory saved: {content}"


# --- Agent Loop ---
async def agent_loop(
    db: AsyncSession,
    user: User,
    conversation_id: int,
    branch_id: Optional[int],
    user_message: str,
    provider: str,
    model: str,
):
    """
    Yields SSE data lines (already JSON-stringified).
    Handles the full agent loop with tool execution.
    """
    # Fetch conversation history
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        yield json.dumps({"type": "error", "message": "Conversation not found"})
        return

    # Save user message
    user_msg = Message(
        conversation_id=conversation_id,
        branch_id=branch_id,
        role="user",
        content=user_message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Build messages for LLM
    system_prompt = await build_system_prompt(db, user)
    messages = [{"role": "system", "content": system_prompt}]

    # Add recent history (last 20 messages)
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where((Message.branch_id == branch_id) | (Message.branch_id.is_(None)))
        .order_by(Message.created_at)
        .limit(20)
    )
    for msg in history_result.scalars().all():
        m = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            m["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            m["tool_call_id"] = msg.tool_call_id
            m["name"] = msg.tool_name or "tool"
        messages.append(m)

    # Add latest user message (already in history, but ensure it's last)
    if messages[-1]["role"] != "user" or messages[-1]["content"] != user_message:
        messages.append({"role": "user", "content": user_message})

    # Gather MCP tools
    mcp_result = await db.execute(
        select(MCPServer).where(MCPServer.user_id == user.id)
    )
    user_mcp_servers = mcp_result.scalars().all()
    mcp_tools = await active_mcp_tools_for_user(user_mcp_servers)

    # Define built-in tools
    builtin_tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the internet for current information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_memory",
                "description": "Save a fact about the user for future conversations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The fact to remember"},
                    },
                    "required": ["content"],
                },
            },
        },
    ]

    all_tools = builtin_tools + mcp_tools

    # Agent iterations
    llm_client = get_llm_client(provider)
    total_tokens = 0

    for iteration in range(settings.MAX_AGENT_ITERATIONS):
        try:
            # Stream LLM response
            assistant_content = ""
            assistant_tool_calls = []

            async for line in llm_client.chat_completion_stream(
                messages=messages,
                model=model,
                tools=all_tools if all_tools else None,
            ):
                data = json.loads(line)

                if data["type"] == "content":
                    assistant_content += data["content"]
                    yield line  # forward to client

                elif data["type"] == "tool_calls":
                    # Accumulate tool calls
                    for tc in data["tool_calls"]:
                        assistant_tool_calls.append(tc)
                    yield line

                elif data["type"] == "finish":
                    if data.get("usage"):
                        total_tokens += data["usage"].get("total_tokens", 0)
                    yield line

                elif data["type"] == "done":
                    break

            # Save assistant message to DB
            clean_content, thought = parse_chain_of_thought(assistant_content)
            assistant_msg = Message(
                conversation_id=conversation_id,
                branch_id=branch_id,
                role="assistant",
                content=clean_content,
                tool_calls=assistant_tool_calls if assistant_tool_calls else None,
                model_used=model,
                tokens_used=total_tokens,
                chain_of_thought=thought,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            # No tool calls — we're done
            if not assistant_tool_calls:
                yield json.dumps({"type": "done"})
                return

            # Process tool calls
            for tc in assistant_tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    arguments = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}

                yield json.dumps({
                    "type": "tool_start",
                    "tool_name": tool_name,
                })

                result = ""
                if tool_name == "web_search":
                    search_result = await tavily_search(
                        arguments.get("query", ""),
                        arguments.get("max_results", 5),
                    )
                    result = json.dumps(search_result, ensure_ascii=False)
                elif tool_name == "save_memory":
                    result = await save_user_memory(
                        db, user.id, arguments.get("content", "")
                    )
                elif tool_name.startswith("mcp__"):
                    result = await execute_mcp_tool(tool_name, arguments)
                else:
                    result = f"Unknown tool: {tool_name}"

                yield json.dumps({
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": result,
                })

                # Save tool result as message
                tool_msg = Message(
                    conversation_id=conversation_id,
                    branch_id=branch_id,
                    role="tool",
                    content=result,
                    tool_call_id=tc.get("id", ""),
                    tool_name=tool_name,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(tool_msg)
                await db.commit()

                # Append to conversation for next iteration
                messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": [tc],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": tool_name,
                    "content": result,
                })

        except LLMClientError as e:
            yield json.dumps({"type": "error", "message": str(e)})
            return
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"Agent error: {str(e)}"})
            return

    # Max iterations reached
    yield json.dumps({
        "type": "error",
        "message": f"Maximum iterations ({settings.MAX_AGENT_ITERATIONS}) reached.",
    })
    yield json.dumps({"type": "done"})


# --- Endpoint ---
@router.post("")
async def chat_endpoint(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Chat endpoint accepting JSON body, returns SSE stream.
    Body: {"conversation_id": int|null, "message": string, "provider": "groq", "model": "...", "branch_id": int|null}
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    conversation_id = body.get("conversation_id")
    message = body.get("message", "").strip()
    provider = body.get("provider", settings.DEFAULT_LLM_PROVIDER)
    model = body.get("model", settings.DEFAULT_MODEL)
    branch_id = body.get("branch_id")

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Create new conversation if needed
    if not conversation_id:
        conv = Conversation(
            user_id=user.id,
            title=message[:50] + "..." if len(message) > 50 else message,
            model_provider=provider,
            model_name=model,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conversation_id = conv.id

        # Yield the new conversation info first
        async def stream_with_info():
            yield f"data: {json.dumps({'type': 'conversation', 'conversation': conv.to_dict()})}\n\n"
            async for line in agent_loop(db, user, conversation_id, branch_id, message, provider, model):
                yield f"data: {line}\n\n"

        return StreamingResponse(
            stream_with_info(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Existing conversation
    return StreamingResponse(
        (f"data: {line}\n\n" async for line in agent_loop(
            db, user, conversation_id, branch_id, message, provider, model
        )),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
