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

@pytest.mark.asyncio
async def test_server_shutdown_errors():
    """Test server error handling during shutdown"""
    server = MCPTerminalServer()
    
    # Test transport disconnection error
    failing_transport = MockTransport(should_fail_disconnect=True)
    await server.start(failing_transport)
    assert server.is_running() == True
    
    with pytest.raises(ServerError) as exc_info:
        await server.stop()
    assert "Failed to disconnect transport" in str(exc_info.value)
    
    # Server should still be marked as stopped even if transport fails
    assert server.is_running() == False
    assert failing_transport.is_connected == True  # Transport remains connected due to failure

@pytest.mark.asyncio
async def test_protocol_errors():
    """Test server handling of protocol-level errors"""
    server = MCPTerminalServer()
    transport = MockTransport()
    
    # Start server
    await server.start(transport)
    
    # Test invalid message handling
    with pytest.raises(ServerError) as exc_info:
        await server.handle_message({"type": "invalid_type"})
    assert "Unsupported message type" in str(exc_info.value)
    
    # Test malformed message
    with pytest.raises(ServerError) as exc_info:
        await server.handle_message(None)
    assert "Invalid message format" in str(exc_info.value)
    
    # Test missing required fields
    with pytest.raises(ServerError) as exc_info:
        await server.handle_message({})
    assert "Missing required field: type" in str(exc_info.value)
    
    # Cleanup
    await server.stop()

@pytest.mark.asyncio
async def test_transport_errors():
    """Test server handling of transport-level errors"""
    server = MCPTerminalServer()
    transport = MockTransport()
    
    await server.start(transport)
    
    # Test send failure
    transport.should_fail_send = True
    with pytest.raises(ServerError) as exc_info:
        await server.send_message({"type": "test"})
    assert "Failed to send message" in str(exc_info.value)
    
    # Test receive failure
    transport.should_fail_receive = True
    with pytest.raises(ServerError) as exc_info:
        await server.receive_message()
    assert "Failed to receive message" in str(exc_info.value)
    
    # Test transport disconnect during operation
    transport.should_disconnect = True
    with pytest.raises(ServerError) as exc_info:
        await server.send_message({"type": "test"})
    assert "Transport disconnected unexpectedly" in str(exc_info.value)
    assert server.is_running() == False
    
    # Cleanup
    await server.stop()

@pytest.mark.asyncio
async def test_unexpected_errors():
    """Test server handling of unexpected errors"""
    server = MCPTerminalServer()
    transport = MockTransport()
    
    await server.start(transport)
    
    # Test handler error
    server.request_handlers["test"] = lambda msg: 1/0  # Will raise ZeroDivisionError
    with pytest.raises(ServerError) as exc_info:
        await server.handle_message({"type": "test"})
    assert "Internal server error" in str(exc_info.value)
    
    # Test message serialization error
    with pytest.raises(ServerError) as exc_info:
        await server.send_message({"type": "test", "data": object()})  # Unserializable object
    assert "Failed to serialize message" in str(exc_info.value)
    
    # Cleanup
    await server.stop()

@pytest.mark.asyncio
async def test_server_status():
    """Test server status reporting"""
    server = MCPTerminalServer()
    transport = MockTransport()
    
    # Test initial status
    status = server.get_status()
    assert status["state"] == "stopped"
    assert status["uptime"] == 0
    assert status["message_count"] == {"sent": 0, "received": 0, "errors": 0}
    
    # Test running status
    await server.start(transport)
    status = server.get_status()
    assert status["state"] == "running"
    assert status["uptime"] > 0
    assert status["message_count"] == {"sent": 0, "received": 0, "errors": 0}
    
    # Test message counting
    await server.send_message({"type": "test"})
    await server.receive_message()
    
    try:
        await server.handle_message({"type": "invalid"})
    except ServerError:
        pass
        
    status = server.get_status()
    assert status["message_count"] == {"sent": 1, "received": 1, "errors": 1}
    
    # Test stopped status
    await server.stop()
    status = server.get_status()
    assert status["state"] == "stopped"
    assert status["uptime"] == 0
    assert status["message_count"] == {"sent": 0, "received": 0, "errors": 0}

@pytest.mark.asyncio
async def test_server_metrics():
    """Test server metrics collection"""
    server = MCPTerminalServer()
    transport = MockTransport()
    
    # Test initial metrics
    metrics = server.get_metrics()
    assert "message_latency_ms" in metrics
    assert metrics["message_latency_ms"]["avg"] == 0
    assert metrics["message_latency_ms"]["max"] == 0
    assert metrics["message_latency_ms"]["min"] == 0
    
    await server.start(transport)
    
    # Test metrics after some activity
    transport.add_latency = 50  # Add 50ms latency
    await server.send_message({"type": "test"})
    await server.receive_message()
    
    transport.add_latency = 150  # Add 150ms latency
    await server.send_message({"type": "test"})
    await server.receive_message()
    
    metrics = server.get_metrics()
    assert metrics["message_latency_ms"]["avg"] == 100  # (50 + 150) / 2
    assert metrics["message_latency_ms"]["max"] == 150
    assert metrics["message_latency_ms"]["min"] == 50
    
    # Cleanup
    await server.stop()

class MockTransport:
    """Mock transport for testing server startup"""
    def __init__(self, should_fail=False, should_fail_disconnect=False):
        self.is_connected = False
        self.should_fail = should_fail
        self.should_fail_disconnect = should_fail_disconnect
        self.should_fail_send = False
        self.should_fail_receive = False
        self.should_disconnect = False
        self.add_latency = 0  # Simulated latency in ms
        
    async def connect(self):
        """Mock transport connection"""
        if self.should_fail:
            raise Exception("Connection failed")
        self.is_connected = True
        
    async def disconnect(self):
        """Mock transport disconnection"""
        if self.should_fail_disconnect:
            raise Exception("Disconnection failed")
        self.is_connected = False
        
    async def send(self, message):
        """Mock message sending"""
        if not self.is_connected or self.should_disconnect:
            self.is_connected = False
            raise Exception("Transport disconnected")
        if self.should_fail_send:
            raise Exception("Send failed")
        if self.add_latency:
            import asyncio
            await asyncio.sleep(self.add_latency / 1000)  # Convert ms to seconds
            
    async def receive(self):
        """Mock message receiving"""
        if not self.is_connected or self.should_disconnect:
            self.is_connected = False
            raise Exception("Transport disconnected")
        if self.should_fail_receive:
            raise Exception("Receive failed")
        if self.add_latency:
            import asyncio
            await asyncio.sleep(self.add_latency / 1000)  # Convert ms to seconds
        return {"type": "test"}