"""MCP Terminal Server Implementation"""

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp_terminal.errors import ServerError
import time

class MCPTerminalServer(Server):
    """MCP server providing terminal access"""
    
    def __init__(self):
        # Initialize request handlers before calling get_capabilities
        self.request_handlers = {}
        self._running = False
        self._transport = None
        
        # Initialize metrics
        self._start_time = None
        self._message_counts = {"sent": 0, "received": 0, "errors": 0}
        self._latency_stats = {"min": 0, "max": 0, "avg": 0, "total": 0, "count": 0}
        
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
            self._start_time = time.time()
            # Reset metrics on start
            self._message_counts = {"sent": 0, "received": 0, "errors": 0}
            self._latency_stats = {"min": 0, "max": 0, "avg": 0, "total": 0, "count": 0}
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
                self._start_time = None
                # Reset metrics
                self._message_counts = {"sent": 0, "received": 0, "errors": 0}
                self._latency_stats = {"min": 0, "max": 0, "avg": 0, "total": 0, "count": 0}
                raise ServerError(f"Failed to disconnect transport: {str(e)}") from e
            self._transport = None
        self._running = False
        self._start_time = None
        # Reset metrics
        self._message_counts = {"sent": 0, "received": 0, "errors": 0}
        self._latency_stats = {"min": 0, "max": 0, "avg": 0, "total": 0, "count": 0}

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
            self._message_counts["errors"] += 1
            raise ServerError(f"Unsupported message type: {msg_type}")
            
        try:
            handler = self.request_handlers[msg_type]
            await handler(message)
        except Exception as e:
            self._message_counts["errors"] += 1
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
                self._message_counts["errors"] += 1
                raise ServerError(f"Failed to serialize message: {str(e)}") from e
                
            start_time = time.time()
            await self._transport.send(message)
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            self._update_latency_stats(latency)
            self._message_counts["sent"] += 1
        except ServerError:
            raise
        except Exception as e:
            self._message_counts["errors"] += 1
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
            start_time = time.time()
            message = await self._transport.receive()
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            self._update_latency_stats(latency)
            self._message_counts["received"] += 1
            return message
        except Exception as e:
            self._message_counts["errors"] += 1
            if "disconnected" in str(e).lower():
                self._running = False
                raise ServerError("Transport disconnected unexpectedly") from e
            raise ServerError(f"Failed to receive message: {str(e)}") from e

    def get_status(self):
        """Get current server status
        
        Returns:
            dict: Server status information
        """
        uptime = 0
        if self._start_time and self.is_running():
            uptime = max(0, int(time.time() - self._start_time))
            
        status = {
            "state": "running" if self.is_running() else "stopped",
            "uptime": uptime,
            "message_counts": self._message_counts.copy()
        }
        return status

    def get_metrics(self):
        """Get server metrics
        
        Returns:
            dict: Server metrics
        """
        return {
            "message_latency_ms": {
                "min": self._latency_stats["min"],
                "max": self._latency_stats["max"],
                "avg": self._latency_stats["avg"]
            }
        }

    def _update_latency_stats(self, latency_ms):
        """Update latency statistics with a new measurement"""
        stats = self._latency_stats
        if stats["count"] == 0:
            stats["min"] = latency_ms
            stats["max"] = latency_ms
            stats["avg"] = latency_ms
        else:
            stats["min"] = min(stats["min"], latency_ms)
            stats["max"] = max(stats["max"], latency_ms)
            
        stats["total"] += latency_ms
        stats["count"] += 1
        stats["avg"] = stats["total"] / stats["count"]