"""MCP Terminal Server Implementation"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

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
        self._transport = transport
        await self._transport.connect()
        self._running = True

    async def stop(self):
        """Stop the server and cleanup"""
        if self._transport:
            await self._transport.disconnect()
            self._transport = None
        self._running = False

    def is_running(self) -> bool:
        """Check if server is currently running"""
        return self._running