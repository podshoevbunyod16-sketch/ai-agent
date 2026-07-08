"""
MCP Client Manager — manages connections to MCP servers via the official MCP Python SDK.
Supports stdio and SSE transports. Maintains a session pool.

Tested with:
  npx -y @modelcontextprotocol/server-filesystem /tmp
  npx -y @modelcontextprotocol/server-fetch

Requires: pip install mcp==1.0.0
"""
import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from app.core.config import settings


class MCPServerConnection:
    """Holds an active MCP client session."""

    def __init__(self, server_id: int, name: str, session: ClientSession, cleanup):
        self.server_id = server_id
        self.name = name
        self.session = session
        self._cleanup = cleanup
        self.tools: List[dict] = []

    async def list_tools(self) -> List[dict]:
        """Fetch available tools from the MCP server."""
        try:
            result = await self.session.list_tools()
            self.tools = []
            for tool in result.tools:
                self.tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                })
            return self.tools
        except Exception as e:
            print(f"[MCP] Error listing tools for {self.name}: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool on the MCP server. Returns result as string."""
        try:
            result = await self.session.call_tool(tool_name, arguments=arguments)
            # Extract text content
            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
                elif isinstance(content, str):
                    texts.append(content)
            return "\n".join(texts) if texts else "Tool returned no text output."
        except Exception as e:
            return f"Error calling tool {tool_name}: {str(e)}"

    async def close(self):
        await self._cleanup()


class MCPClientManager:
    """Manages multiple MCP server connections."""

    def __init__(self):
        self._connections: Dict[int, MCPServerConnection] = {}
        self._exit_stack = AsyncExitStack()

    async def connect_stdio(
        self, server_id: int, name: str, command: str, env_vars: Optional[dict] = None
    ) -> MCPServerConnection:
        """
        Connect to an MCP server via stdio.
        command: e.g. "npx -y @modelcontextprotocol/server-filesystem /tmp"
        """
        # Parse command into parts
        parts = command.split()
        if not parts:
            raise ValueError("Empty command")

        # Merge env vars
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        server_params = StdioServerParameters(
            command=parts[0],
            args=parts[1:],
            env=env,
        )

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()

        conn = MCPServerConnection(
            server_id=server_id,
            name=name,
            session=session,
            cleanup=self._make_cleanup(server_id),
        )
        self._connections[server_id] = conn
        return conn

    async def connect_sse(
        self, server_id: int, name: str, url: str
    ) -> MCPServerConnection:
        """Connect to an MCP server via SSE endpoint."""
        sse_transport = await self._exit_stack.enter_async_context(
            sse_client(url)
        )
        read, write = sse_transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()

        conn = MCPServerConnection(
            server_id=server_id,
            name=name,
            session=session,
            cleanup=self._make_cleanup(server_id),
        )
        self._connections[server_id] = conn
        return conn

    def _make_cleanup(self, server_id: int):
        async def cleanup():
            if server_id in self._connections:
                del self._connections[server_id]
        return cleanup

    def get_connection(self, server_id: int) -> Optional[MCPServerConnection]:
        return self._connections.get(server_id)

    def get_all_connections(self) -> List[MCPServerConnection]:
        return list(self._connections.values())

    async def disconnect(self, server_id: int):
        conn = self._connections.pop(server_id, None)
        if conn:
            await conn.close()

    async def disconnect_all(self):
        for conn in list(self._connections.values()):
            await conn.close()
        self._connections.clear()
        await self._exit_stack.aclose()


# Singleton
_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
    return _mcp_manager


async def active_mcp_tools_for_user(user_mcp_servers: list) -> List[dict]:
    """
    Connect to all enabled MCP servers for a user and collect their tools.
    Each tool is annotated with mcp_server_id for routing.
    Returns tools in OpenAI function-calling format.
    """
    manager = get_mcp_manager()
    all_tools = []

    for srv in user_mcp_servers:
        if not srv.enabled:
            continue
        try:
            if srv.transport_type == "stdio" and srv.command:
                conn = await manager.connect_stdio(
                    server_id=srv.id,
                    name=srv.name,
                    command=srv.command,
                    env_vars=srv.env_vars,
                )
            elif srv.transport_type == "sse" and srv.url:
                conn = await manager.connect_sse(
                    server_id=srv.id,
                    name=srv.name,
                    url=srv.url,
                )
            else:
                continue

            tools = await conn.list_tools()
            for t in tools:
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": f"mcp__{srv.id}__{t['name']}",
                        "description": f"[{srv.name}] {t['description']}",
                        "parameters": t["input_schema"],
                    },
                }
                all_tools.append(tool_def)
        except Exception as e:
            print(f"[MCP] Failed to connect to {srv.name}: {e}")
            continue

    return all_tools


async def execute_mcp_tool(tool_name: str, arguments: dict) -> str:
    """
    Execute an MCP tool by its prefixed name: mcp__{server_id}__{tool_name}.
    """
    manager = get_mcp_manager()
    parts = tool_name.split("__", 2)
    if len(parts) != 3 or parts[0] != "mcp":
        return f"Invalid MCP tool name format: {tool_name}"

    try:
        server_id = int(parts[1])
        actual_tool_name = parts[2]
    except ValueError:
        return f"Invalid server ID in tool name: {tool_name}"

    conn = manager.get_connection(server_id)
    if not conn:
        return f"MCP server {server_id} not connected."

    return await conn.call_tool(actual_tool_name, arguments)
