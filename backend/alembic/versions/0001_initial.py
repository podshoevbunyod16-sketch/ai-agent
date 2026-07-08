"""Initial migration — all tables"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("firebase_uid", sa.String(128), unique=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(50), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("photo_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), default="Новый чат", nullable=False),
        sa.Column("pinned", sa.Boolean(), default=False, nullable=False),
        sa.Column("model_provider", sa.String(50), default="groq", nullable=False),
        sa.Column("model_name", sa.String(100), default="llama-3.3-70b-versatile", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("branch_number", sa.Integer(), default=1, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), default="", nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_call_id", sa.String(100), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("chain_of_thought", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_branch_id", "messages", ["branch_id"])

    op.create_table(
        "memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("importance", sa.Float(), default=1.0, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("transport_type", sa.String(20), default="stdio", nullable=False),
        sa.Column("command", sa.String(255), nullable=True),
        sa.Column("url", sa.String(512), nullable=True),
        sa.Column("env_vars", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), default=True, nullable=False),
        sa.Column("tools_cache", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mcp_servers")
    op.drop_table("memories")
    op.drop_table("messages")
    op.drop_table("branches")
    op.drop_table("conversations")
    op.drop_table("users")
