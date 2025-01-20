import pytest
from mcp.server import Server
from mcp_terminal.server import MCPTerminalServer
from mcp_terminal.errors import ServerError

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

@pytest.mark.asyncio
async def test_server_startup_errors():
    """Test server error handling during startup"""
    server = MCPTerminalServer()

    # Test transport connection error
    failing_transport = MockTransport(should_fail=True)
    with pytest.raises(ServerError) as exc_info:
        await server.start(failing_transport)
    assert "Failed to connect transport" in str(exc_info.value)
    assert server.is_running() == False

    # Test double start error
    transport = MockTransport()
    await server.start(transport)
    with pytest.raises(ServerError) as exc_info:
        await server.start(transport)
    assert "Server is already running" in str(exc_info.value)
    
    # Cleanup
    await server.stop()

class MockTransport:
    """Mock transport for testing server startup"""
    def __init__(self, should_fail=False):
        self.is_connected = False
        self.should_fail = should_fail
        
    async def connect(self):
        """Mock transport connection"""
        if self.should_fail:
            raise Exception("Connection failed")
        self.is_connected = True
        
    async def disconnect(self):
        """Mock transport disconnection"""
        self.is_connected = False