"""Tests for the MCP Terminal Server protocol implementation."""

import asyncio
import json
import pytest
from datetime import datetime
from mcp_terminal.server import MCPTerminalServer

class MockTransport(asyncio.Transport):
    """Mock transport for testing."""
    def __init__(self):
        super().__init__()
        self.buffer = bytearray()
        self._closing = False
        
    def write(self, data):
        """Store written data in buffer."""
        self.buffer.extend(data)
        
    def get_write_buffer(self):
        """Get and clear the write buffer."""
        data = bytes(self.buffer)
        self.buffer.clear()
        return data
        
    def close(self):
        """Close the transport."""
        self._closing = True
        
    def is_closing(self):
        """Return True if the transport is closing."""
        return self._closing
        
    def abort(self):
        """Abort the transport."""
        self.close()

@pytest.fixture
async def server():
    """Create a server instance for testing."""
    # Create server with allowed commands
    server = MCPTerminalServer(allowed_commands={"echo", "ls"})
    
    # Create pipes for testing
    server._reader = asyncio.StreamReader()
    writer_transport = MockTransport()
    writer_protocol = asyncio.StreamReaderProtocol(asyncio.StreamReader())
    server._writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())
    
    return server

@pytest.mark.asyncio
async def test_capabilities_message(server):
    """Test that the server sends correct capabilities message."""
    server = await server
    
    # Capture the capabilities message
    await server._send_capabilities()
    
    # Get the written data
    data = server._writer.transport.get_write_buffer()
    message = json.loads(data.decode())
    
    # Verify the message structure
    assert message["protocol"] == "1.0.0"
    assert message["name"] == "terminal"
    assert message["version"] == "1.0.0"
    assert "capabilities" in message
    assert "execute" in message["capabilities"]
    
    # Verify execute capability structure
    execute = message["capabilities"]["execute"]
    assert execute["description"] == "Execute a terminal command"
    assert "command" in execute["parameters"]
    assert execute["parameters"]["command"]["type"] == "string"
    
    # Verify return type structure
    returns = execute["returns"]
    assert returns["type"] == "object"
    assert all(prop in returns["properties"] for prop in ["exitCode", "stdout", "stderr", "startTime", "endTime"])

@pytest.mark.asyncio
async def test_execute_command_message(server):
    """Test handling of execute command message."""
    server = await server
    
    # Create a test message
    message = {
        "type": "execute",
        "data": {
            "command": "echo 'test'"
        }
    }
    
    # Send the message
    await server._handle_message(message)
    
    # Get the response
    data = server._writer.transport.get_write_buffer()
    response = json.loads(data.decode())
    
    # Verify response structure
    assert response["type"] == "result"
    assert "data" in response
    data = response["data"]
    assert data["command"] == "echo 'test'"
    assert data["exitCode"] == 0
    assert "test" in data["stdout"]
    assert data["stderr"] == ""
    assert datetime.fromisoformat(data["startTime"])  # Should parse without error
    assert datetime.fromisoformat(data["endTime"])    # Should parse without error

@pytest.mark.asyncio
async def test_disallowed_command(server):
    """Test handling of disallowed command."""
    server = await server
    
    message = {
        "type": "execute",
        "data": {
            "command": "rm -rf /"
        }
    }
    
    # Send the message
    await server._handle_message(message)
    
    # Get the error response
    data = server._writer.transport.get_write_buffer()
    response = json.loads(data.decode())
    
    # Verify error structure
    assert response["type"] == "error"
    assert "data" in response
    assert "message" in response["data"]
    assert "not allowed" in response["data"]["message"].lower()

@pytest.mark.asyncio
async def test_invalid_message_type(server):
    """Test handling of invalid message type."""
    server = await server
    
    message = {
        "type": "invalid",
        "data": {}
    }
    
    # Send the message
    await server._handle_message(message)
    
    # Get the error response
    data = server._writer.transport.get_write_buffer()
    response = json.loads(data.decode())
    
    # Verify error structure
    assert response["type"] == "error"
    assert "data" in response
    assert "message" in response["data"]
    assert "unknown message type" in response["data"]["message"].lower()

@pytest.mark.asyncio
async def test_missing_command(server):
    """Test handling of missing command parameter."""
    server = await server
    
    message = {
        "type": "execute",
        "data": {}
    }
    
    # Send the message
    await server._handle_message(message)
    
    # Get the error response
    data = server._writer.transport.get_write_buffer()
    response = json.loads(data.decode())
    
    # Verify error structure
    assert response["type"] == "error"
    assert "data" in response
    assert "message" in response["data"]
    assert "missing command parameter" in response["data"]["message"].lower()

@pytest.mark.asyncio
async def test_invalid_json_message(server):
    """Test handling of invalid JSON message."""
    server = await server
    
    # Simulate receiving invalid JSON
    server._reader.feed_data(b"invalid json\n")
    
    # Try to read the message
    message = await server._read_message()
    
    # Should return None for invalid JSON
    assert message is None
    
    # Get the error response
    data = server._writer.transport.get_write_buffer()
    response = json.loads(data.decode())
    
    # Verify error structure
    assert response["type"] == "error"
    assert "data" in response
    assert "message" in response["data"]
    assert "invalid json" in response["data"]["message"].lower() 