"""
SQLAlchemy models for AI Chat Agent.
All tables use async-compatible types. Primary keys are auto-increment integers.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Float,
    Index,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    firebase_uid = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    display_name = Column(String(255), nullable=True)
    photo_url = Column(String(512), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    conversations = relationship("Conversation", back_populates="user", lazy="selectin")
    memories = relationship("Memory", back_populates="user", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "firebase_uid": self.firebase_uid,
            "email": self.email,
            "phone_number": self.phone_number,
            "display_name": self.display_name,
            "photo_url": self.photo_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="Новый чат", nullable=False)
    pinned = Column(Boolean, default=False, nullable=False)
    model_provider = Column(String(50), default="groq", nullable=False)
    model_name = Column(String(100), default="llama-3.3-70b-versatile", nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", lazy="selectin",
        order_by="Message.created_at",
    )
    branches = relationship("Branch", back_populates="conversation", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "pinned": self.pinned,
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    branch_id = Column(
        Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    role = Column(String(20), nullable=False)  # system / user / assistant / tool
    content = Column(Text, nullable=False, default="")
    tool_calls = Column(JSON, nullable=True)      # list of tool calls from LLM
    tool_call_id = Column(String(100), nullable=True)  # which tool call this result belongs to
    tool_name = Column(String(100), nullable=True)     # name of executed tool
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    chain_of_thought = Column(Text, nullable=True)  # parsed <thinking> block
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    conversation = relationship("Conversation", back_populates="messages")
    branch = relationship("Branch", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_branch_id", "branch_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "branch_id": self.branch_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "chain_of_thought": self.chain_of_thought,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Branch(Base):
    """Dialogue branching: when user edits a sent message."""
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    parent_branch_id = Column(
        Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    branch_number = Column(Integer, default=1, nullable=False)  # sequential within conversation
    title = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    conversation = relationship("Conversation", back_populates="branches")
    messages = relationship(
        "Message", back_populates="branch", lazy="selectin",
        order_by="Message.created_at",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "parent_branch_id": self.parent_branch_id,
            "branch_number": self.branch_number,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Memory(Base):
    """Facts saved by the agent for personalization."""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    source_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    importance = Column(Float, default=1.0, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="memories")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "source_message_id": self.source_message_id,
            "importance": self.importance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MCPServer(Base):
    """Registered MCP servers (filesystem, fetch, etc.)."""
    __tablename__ = "mcp_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    transport_type = Column(String(20), default="stdio", nullable=False)  # stdio / sse
    command = Column(String(255), nullable=True)       # for stdio (e.g., "npx -y @modelcontextprotocol/server-filesystem /tmp")
    url = Column(String(512), nullable=True)           # for sse
    env_vars = Column(JSON, default=dict, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    tools_cache = Column(JSON, nullable=True)          # cached tools/list response
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "transport_type": self.transport_type,
            "command": self.command,
            "url": self.url,
            "env_vars": self.env_vars,
            "enabled": self.enabled,
            "tools_cache": self.tools_cache,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
