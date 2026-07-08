"""
FastAPI entry point — AI Chat Agent Backend.

Routes:
  GET  /health           — health check
  GET  /api/auth/me      — current user
  GET  /api/auth/models  — available LLM models
  POST /api/chat         — chat with SSE streaming
  GET  /api/conversations — list conversations
  GET  /api/conversations/{id} — get conversation
  POST /api/conversations — create conversation
  PATCH /api/conversations/{id} — update
  DELETE /api/conversations/{id} — delete
  GET  /api/conversations/{id}/messages — messages
  POST /api/conversations/{id}/branches — create branch
  GET  /api/conversations/search — search
  GET  /api/conversations/{id}/export — export
  GET  /api/mcp/servers — list MCP servers
  POST /api/mcp/servers — add MCP server
  PATCH /api/mcp/servers/{id} — update
  DELETE /api/mcp/servers/{id} — delete
  POST /api/mcp/servers/{id}/test — test connection
  POST /api/mcp/servers/{id}/toggle — toggle enable

Startup:
  - Initialize DB tables
  - Connect Firebase Admin SDK

Shutdown:
  - Disconnect all MCP sessions
  - Close DB engine
"""
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import init_db, async_engine
from app.api import health, auth, chat, conversations, mcp as mcp_router
from app.mcp.mcp_client_manager import get_mcp_manager

# Rate limiter: 30 requests per minute per IP
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AI Chat Agent API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(mcp_router.router)


@app.on_event("startup")
async def startup():
    """Initialize database tables on startup."""
    await init_db()
    print(f"[STARTUP] Database initialized: {settings.DATABASE_URL[:50]}...")
    print(f"[STARTUP] LLM Provider: {settings.DEFAULT_LLM_PROVIDER}")
    print(f"[STARTUP] CORS origins: {settings.allowed_origins_list}")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    manager = get_mcp_manager()
    await manager.disconnect_all()
    await async_engine.dispose()
    print("[SHUTDOWN] Cleaned up MCP connections and DB engine.")
