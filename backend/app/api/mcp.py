"""
MCP Server management endpoints.
  GET    /api/mcp/servers          — list user's MCP servers
  POST   /api/mcp/servers          — add new MCP server
  PATCH  /api/mcp/servers/{id}     — update server
  DELETE /api/mcp/servers/{id}     — remove server
  POST   /api/mcp/servers/{id}/test — test connection, return tools/list
  POST   /api/mcp/servers/{id}/toggle — enable/disable
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import MCPServer, User
from app.mcp.mcp_client_manager import get_mcp_manager
from app.utils.firebase_auth import get_current_user

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/servers")
async def list_servers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all MCP servers for the current user."""
    result = await db.execute(
        select(MCPServer).where(MCPServer.user_id == user.id)
    )
    servers = result.scalars().all()
    return {"servers": [s.to_dict() for s in servers]}


@router.post("/servers")
async def create_server(
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a new MCP server."""
    server = MCPServer(
        user_id=user.id,
        name=data["name"],
        transport_type=data.get("transport_type", "stdio"),
        command=data.get("command"),
        url=data.get("url"),
        env_vars=data.get("env_vars"),
        enabled=data.get("enabled", True),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server.to_dict()


@router.patch("/servers/{server_id}")
async def update_server(
    server_id: int,
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update MCP server configuration."""
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.user_id == user.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    for field in ["name", "transport_type", "command", "url", "env_vars", "enabled"]:
        if field in data:
            setattr(server, field, data[field])

    server.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(server)
    return server.to_dict()


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an MCP server."""
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.user_id == user.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    await db.delete(server)
    await db.commit()
    return {"deleted": True}


@router.post("/servers/{server_id}/test")
async def test_server(
    server_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test connection to an MCP server and return available tools."""
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.user_id == user.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    manager = get_mcp_manager()
    try:
        if server.transport_type == "stdio" and server.command:
            conn = await manager.connect_stdio(
                server_id=server.id,
                name=server.name,
                command=server.command,
                env_vars=server.env_vars,
            )
        elif server.transport_type == "sse" and server.url:
            conn = await manager.connect_sse(
                server_id=server.id,
                name=server.name,
                url=server.url,
            )
        else:
            return {"error": "Invalid server configuration"}

        tools = await conn.list_tools()

        # Cache tools in DB
        server.tools_cache = tools
        await db.commit()

        return {"connected": True, "tools": tools}

    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/servers/{server_id}/toggle")
async def toggle_server(
    server_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle server enabled/disabled."""
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.user_id == user.id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server.enabled = not server.enabled
    server.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(server)
    return server.to_dict()
