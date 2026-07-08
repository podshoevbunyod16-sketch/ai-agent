"""
Conversation CRUD + message history + search + export.
All routes require Firebase authentication.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.models import Conversation, Message, Branch, User
from app.utils.firebase_auth import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the current user."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    return {"conversations": [c.to_dict() for c in conversations]}


@router.get("/{conv_id}")
async def get_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single conversation with all messages."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages for the main branch (no branch_id)
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .where(Message.branch_id.is_(None))
        .order_by(Message.created_at)
    )
    messages = [m.to_dict() for m in msg_result.scalars().all()]

    # Get branches
    branch_result = await db.execute(
        select(Branch).where(Branch.conversation_id == conv_id)
    )
    branches = [b.to_dict() for b in branch_result.scalars().all()]

    return {
        "conversation": conv.to_dict(),
        "messages": messages,
        "branches": branches,
    }


@router.post("")
async def create_conversation(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    conv = Conversation(
        user_id=user.id,
        title=data.get("title", "Новый чат"),
        model_provider=data.get("provider", "groq"),
        model_name=data.get("model", "llama-3.3-70b-versatile"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv.to_dict()


@router.patch("/{conv_id}")
async def update_conversation(
    conv_id: int,
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update conversation (title, pinned, model)."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if "title" in data:
        conv.title = data["title"]
    if "pinned" in data:
        conv.pinned = data["pinned"]
    if "model_provider" in data:
        conv.model_provider = data["model_provider"]
    if "model_name" in data:
        conv.model_name = data["model_name"]

    conv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(conv)
    return conv.to_dict()


@router.delete("/{conv_id}")
async def delete_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return {"deleted": True}


@router.get("/{conv_id}/messages")
async def get_messages(
    conv_id: int,
    branch_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a conversation, optionally filtered by branch."""
    q = select(Message).where(Message.conversation_id == conv_id)
    if branch_id is not None:
        q = q.where(Message.branch_id == branch_id)
    else:
        q = q.where(Message.branch_id.is_(None))

    result = await db.execute(q.order_by(Message.created_at))
    return {"messages": [m.to_dict() for m in result.scalars().all()]}


@router.post("/{conv_id}/branches")
async def create_branch(
    conv_id: int,
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new branch for editing a message."""
    # Count existing branches for numbering
    result = await db.execute(
        select(func.count(Branch.id)).where(Branch.conversation_id == conv_id)
    )
    count = result.scalar() or 0

    branch = Branch(
        conversation_id=conv_id,
        parent_branch_id=data.get("parent_branch_id"),
        branch_number=count + 1,
        title=data.get("title"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch.to_dict()


@router.get("/search")
async def search_conversations(
    q: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across conversation titles and message contents."""
    if not q or len(q) < 2:
        return {"results": []}

    # Search in messages (content LIKE)
    result = await db.execute(
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
        .where(Message.content.ilike(f"%{q}%"))
        .order_by(Message.created_at.desc())
        .limit(50)
    )

    hits = []
    seen_conv_ids = set()
    for msg, conv in result.all():
        if conv.id not in seen_conv_ids:
            seen_conv_ids.add(conv.id)
            hits.append({
                "conversation": conv.to_dict(),
                "matched_message": msg.to_dict(),
            })

    return {"results": hits}


@router.get("/{conv_id}/export")
async def export_conversation(
    conv_id: int,
    format: str = "markdown",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export conversation as markdown or JSON."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .where(Message.branch_id.is_(None))
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    if format == "json":
        return {
            "conversation": conv.to_dict(),
            "messages": [m.to_dict() for m in messages],
        }

    # Markdown export
    lines = [f"# {conv.title}\n", f"Date: {conv.created_at}\n", "---\n"]
    for m in messages:
        role_label = "User" if m.role == "user" else "Assistant" if m.role == "assistant" else "Tool"
        lines.append(f"**{role_label}:**\n{m.content}\n")
        if m.chain_of_thought:
            lines.append(f"*Thought: {m.chain_of_thought}*\n")
    return {"markdown": "\n".join(lines)}
