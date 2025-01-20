"""MCP Terminal Server Implementation"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions

class MCPTerminalServer(Server):
    """MCP server providing terminal access"""
    
    def __init__(self):
        # Initialize request handlers before calling get_capabilities
        self.request_handlers = {}
        
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