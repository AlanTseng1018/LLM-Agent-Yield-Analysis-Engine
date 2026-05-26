"""
MCP HTTP client – connects to the running MCP server and lists available tools.
"""

from __future__ import annotations

MCP_URL = "http://localhost:8001/mcp"


async def list_tools(url: str = MCP_URL) -> list[dict]:
    """
    Connect to the MCP server and return a list of tool descriptors.

    Each dict:
        name        : str
        description : str
        parameters  : dict  (JSON Schema of input parameters)
    """
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

    return [
        {
            "name": t.name,
            "description": t.description or "",
            "parameters": t.inputSchema or {},
        }
        for t in result.tools
    ]


async def call_tool(tool_name: str, arguments: dict, url: str = MCP_URL) -> list[dict]:
    """
    Call a single MCP tool and return its content items.

    Each item: {"type": "text"|"image", "text": str|None, "data": str|None, "mimeType": str|None}
    """
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)

    return [
        {
            "type":     c.type,
            "text":     getattr(c, "text",     None),
            "data":     getattr(c, "data",     None),
            "mimeType": getattr(c, "mimeType", None),
        }
        for c in result.content
    ]
