"""MCP Terminal Server Implementation"""

from typing import Dict, Any, Optional, Callable, Awaitable
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp_terminal.errors import ServerError
import time
import json
from dataclasses import dataclass, asdict

@dataclass
class MetricsState:
    """Server metrics state"""
    min: float = 0
    max: float = 0
    avg: float = 0
    total: float = 0
    count: int = 0

    def update(self, value: float) -> None:
        """Update metrics with a new value"""
        if self.count == 0:
            self.min = value
            self.max = value
            self.avg = value
        else:
            self.min = min(self.min, value)
            self.max = max(self.max, value)
        
        self.total += value
        self.count += 1
        self.avg = self.total / self.count

    def reset(self) -> None:
        """Reset metrics to initial state"""
        self.min = 0
        self.max = 0
        self.avg = 0
        self.total = 0
        self.count = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert metrics to dictionary"""
        return {
            "min": self.min,
            "max": self.max,
            "avg": self.avg
        }

class MCPTerminalServer(Server):
    """MCP server providing terminal access"""
    
    # Server configuration
    SERVER_NAME = "terminal"
    SERVER_VERSION = "0.1.0"
    
    def __init__(self):
        # Initialize request handlers before calling get_capabilities
        self.request_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
        self._running: bool = False
        self._transport: Optional[Any] = None
        self._start_time: Optional[float] = None
        
        # Initialize metrics
        self._message_counts = {"sent": 0, "received": 0, "errors": 0}
        self._latency_stats = MetricsState()
        
        # Initialize capabilities
        notification_options = NotificationOptions()
        experimental_capabilities = {}
        
        initialization_options = InitializationOptions(
            server_name=self.SERVER_NAME,
            server_version=self.SERVER_VERSION,
            capabilities=self.get_capabilities(
                notification_options=notification_options,
                experimental_capabilities=experimental_capabilities
            ),
        )
        
        # Call parent class initialization
        super().__init__(initialization_options.server_name, initialization_options.server_version)

    def _reset_metrics(self) -> None:
        """Reset all server metrics"""
        self._message_counts = {"sent": 0, "received": 0, "errors": 0}
        self._latency_stats.reset()

    async def start(self, transport: Any) -> None:
        """Start the server with the given transport
        
        Args:
            transport: The transport to use for communication
            
        Raises:
            ServerError: If server is already running or transport connection fails
        """
        if self.is_running():
            raise ServerError("Server is already running")

        self._transport = transport
        try:
            await self._transport.connect()
            self._running = True
            self._start_time = time.time()
            self._reset_metrics()
        except Exception as e:
            self._transport = None
            raise ServerError(f"Failed to connect transport: {str(e)}") from e

    async def stop(self) -> None:
        """Stop the server and cleanup
        
        Raises:
            ServerError: If transport disconnection fails
        """
        if self._transport:
            try:
                await self._transport.disconnect()
            except Exception as e:
                # Still mark server as stopped but preserve transport state
                self._running = False
                self._start_time = None
                self._reset_metrics()
                raise ServerError(f"Failed to disconnect transport: {str(e)}") from e
            self._transport = None
        self._running = False
        self._start_time = None
        self._reset_metrics()

    def is_running(self) -> bool:
        """Check if server is currently running
        
        Returns:
            bool: True if server is running, False otherwise
        """
        return self._running

    async def handle_message(self, message: Optional[Dict[str, Any]]) -> None:
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

    async def send_message(self, message: Dict[str, Any]) -> None:
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
            try:
                json.dumps(message)
            except (TypeError, ValueError) as e:
                self._message_counts["errors"] += 1
                raise ServerError(f"Failed to serialize message: {str(e)}") from e
                
            start_time = time.time()
            await self._transport.send(message)
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            self._latency_stats.update(latency)
            self._message_counts["sent"] += 1
        except ServerError:
            raise
        except Exception as e:
            self._message_counts["errors"] += 1
            if "disconnected" in str(e).lower():
                self._running = False
                raise ServerError("Transport disconnected unexpectedly") from e
            raise ServerError(f"Failed to send message: {str(e)}") from e

    async def receive_message(self) -> Dict[str, Any]:
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
            
            self._latency_stats.update(latency)
            self._message_counts["received"] += 1
            return message
        except Exception as e:
            self._message_counts["errors"] += 1
            if "disconnected" in str(e).lower():
                self._running = False
                raise ServerError("Transport disconnected unexpectedly") from e
            raise ServerError(f"Failed to receive message: {str(e)}") from e

    def get_status(self) -> Dict[str, Any]:
        """Get current server status
        
        Returns:
            dict: Server status information containing:
                - state: Current server state (running/stopped)
                - uptime: Server uptime in seconds
                - message_counts: Message counters for sent/received/errors
        """
        uptime = 0
        if self._start_time and self.is_running():
            uptime = max(0, int(time.time() - self._start_time))
            
        return {
            "state": "running" if self.is_running() else "stopped",
            "uptime": uptime,
            "message_counts": self._message_counts.copy()
        }

    def get_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get server metrics
        
        Returns:
            dict: Server metrics containing:
                - message_latency_ms: Message latency statistics (min/max/avg)
        """
        return {
            "message_latency_ms": self._latency_stats.to_dict()
        }