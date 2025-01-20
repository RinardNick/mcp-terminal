import pytest
from mcp.server import Server
from mcp_terminal.server import MCPTerminalServer

def test_server_initialization():
    """Test basic server initialization"""
    server = MCPTerminalServer()
    assert isinstance(server, Server)  # Should inherit from MCP Server
    assert server.name == "terminal"
    assert server.version == "0.1.0"