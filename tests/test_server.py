import pytest
from mcp.server import Server
from mcp_terminal.server import MCPTerminalServer

def test_server_initialization():
    """Test basic server initialization"""
    server = MCPTerminalServer()
    assert isinstance(server, Server)  # Should inherit from MCP Server
    assert server.name == "terminal"
    assert server.version == "0.1.0"

@pytest.mark.asyncio
async def test_server_startup():
    """Test server startup with transport"""
    server = MCPTerminalServer()
    transport = MockTransport()
    
    await server.start(transport)
    assert server.is_running() == True
    assert transport.is_connected == True
    
    # Cleanup
    await server.stop()
    assert server.is_running() == False
    assert transport.is_connected == False

class MockTransport:
    """Mock transport for testing server startup"""
    def __init__(self):
        self.is_connected = False
        
    async def connect(self):
        """Mock transport connection"""
        self.is_connected = True
        
    async def disconnect(self):
        """Mock transport disconnection"""
        self.is_connected = False