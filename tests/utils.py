"""Test utilities for MCP Terminal Server tests"""

import asyncio

class MockTransport:
    """Mock transport for testing server startup"""
    def __init__(self, should_fail: bool = False, should_fail_disconnect: bool = False):
        self.is_connected = False
        self.should_fail = should_fail
        self.should_fail_disconnect = should_fail_disconnect
        self.should_fail_send = False
        self.should_fail_receive = False
        self.should_disconnect = False
        self.add_latency = 0  # Simulated latency in ms
        
    async def connect(self) -> None:
        """Mock transport connection"""
        if self.should_fail:
            raise Exception("Connection failed")
        self.is_connected = True
        
    async def disconnect(self) -> None:
        """Mock transport disconnection"""
        if self.should_fail_disconnect:
            raise Exception("Disconnection failed")
        self.is_connected = False
        
    async def send(self, message: dict) -> None:
        """Mock message sending
        
        Args:
            message: The message to send
            
        Raises:
            Exception: If sending fails or transport is disconnected
        """
        if not self.is_connected or self.should_disconnect:
            self.is_connected = False
            raise Exception("Transport disconnected")
        if self.should_fail_send:
            raise Exception("Send failed")
        if self.add_latency:
            await asyncio.sleep(self.add_latency / 1000)  # Convert ms to seconds
            
    async def receive(self) -> dict:
        """Mock message receiving
        
        Returns:
            dict: The received message
            
        Raises:
            Exception: If receiving fails or transport is disconnected
        """
        if not self.is_connected or self.should_disconnect:
            self.is_connected = False
            raise Exception("Transport disconnected")
        if self.should_fail_receive:
            raise Exception("Receive failed")
        if self.add_latency:
            await asyncio.sleep(self.add_latency / 1000)  # Convert ms to seconds
        return {"type": "test"} 