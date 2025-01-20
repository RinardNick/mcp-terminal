"""MCP Terminal Server Implementation"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp_terminal.errors import ServerError

class MCPTerminalServer(Server):
    """MCP server providing terminal access"""
    
    def __init__(self):
        # Initialize request handlers before calling get_capabilities
        self.request_handlers = {}
        self._running = False
        self._transport = None
        
        notification_options = NotificationOptions()
        experimental_capabilities = {}
        
        initialization_options = InitializationOptions(
            server_name="terminal",
            server_version="0.1.0",
            capabilities=self.get_capabilities(
                notification_options=notification_options,
                experimental_capabilities=experimental_capabilities
            ),
        )
        
        # Call parent class initialization first
        super().__init__(initialization_options.server_name, initialization_options.server_version)

    async def start(self, transport):
        """Start the server with the given transport"""
        if self.is_running():
            raise ServerError("Server is already running")

        self._transport = transport
        try:
            await self._transport.connect()
            self._running = True
        except Exception as e:
            self._transport = None
            raise ServerError(f"Failed to connect transport: {str(e)}") from e

    async def stop(self):
        """Stop the server and cleanup"""
        if self._transport:
            try:
                await self._transport.disconnect()
            except Exception as e:
                # Still mark server as stopped but preserve transport state
                self._running = False
                raise ServerError(f"Failed to disconnect transport: {str(e)}") from e
            self._transport = None
        self._running = False

    def is_running(self) -> bool:
        """Check if server is currently running"""
        return self._running

    async def handle_message(self, message):
        """Handle incoming protocol messages
        
        Args:
            message: The message to process
            
        Raises:
            ServerError: If the message is invalid or unsupported
        """
        if message is None:
            raise ServerError("Invalid message format")
            
        if not isinstance(message, dict):
            raise ServerError("Invalid message format")
            
        if "type" not in message:
            raise ServerError("Missing required field: type")
            
        msg_type = message["type"]
        if msg_type not in self.request_handlers:
            raise ServerError(f"Unsupported message type: {msg_type}")
            
        try:
            handler = self.request_handlers[msg_type]
            await handler(message)
        except Exception as e:
            raise ServerError(f"Internal server error: {str(e)}") from e

    async def send_message(self, message):
        """Send a message through the transport
        
        Args:
            message: The message to send
            
        Raises:
            ServerError: If sending fails or transport is disconnected
        """
        if not self._transport:
            raise ServerError("Server not started")
            
        try:
            # Verify message can be serialized
            import json
            try:
                json.dumps(message)
            except (TypeError, ValueError) as e:
                raise ServerError(f"Failed to serialize message: {str(e)}") from e
                
            await self._transport.send(message)
        except ServerError:
            raise
        except Exception as e:
            if "disconnected" in str(e).lower():
                self._running = False
                raise ServerError("Transport disconnected unexpectedly") from e
            raise ServerError(f"Failed to send message: {str(e)}") from e

    async def receive_message(self):
        """Receive a message from the transport
        
        Returns:
            dict: The received message
            
        Raises:
            ServerError: If receiving fails or transport is disconnected
        """
        if not self._transport:
            raise ServerError("Server not started")
            
        try:
            return await self._transport.receive()
        except Exception as e:
            if "disconnected" in str(e).lower():
                self._running = False
                raise ServerError("Transport disconnected unexpectedly") from e
            raise ServerError(f"Failed to receive message: {str(e)}") from e