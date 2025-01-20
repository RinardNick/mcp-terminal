#!/usr/bin/env python3
"""
MCP Terminal Server - A secure terminal execution server implementing the Model Context Protocol.
"""

import asyncio
import json
import logging
import signal
import sys
from argparse import ArgumentParser
from datetime import datetime, timezone
from typing import Dict, Optional, Set

from mcp_terminal.terminal import TerminalExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp-terminal')

class MCPTerminalServer:
    """
    MCP Terminal Server implementation.
    
    Implements the Model Context Protocol for secure terminal command execution.
    """
    
    def __init__(self, allowed_commands: Optional[Set[str]] = None,
                 timeout_ms: int = 30000,
                 max_output_size: int = 1024 * 1024):
        """
        Initialize the MCP Terminal Server.
        
        Args:
            allowed_commands: Set of allowed command executables
            timeout_ms: Maximum execution time in milliseconds
            max_output_size: Maximum output size in bytes
        """
        self.executor = TerminalExecutor(
            allowed_commands=list(allowed_commands) if allowed_commands else None,
            timeout_ms=timeout_ms,
            max_output_size=max_output_size
        )
        
        # Set up signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._signal_handler)
            
        self._reader = None
        self._writer = None
        
    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        if self._writer:
            self._writer.close()
        sys.exit(0)
        
    async def start(self):
        """Start the MCP server using stdin/stdout for communication."""
        loop = asyncio.get_event_loop()
        
        # Set up stdin reader
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        
        # Set up stdout writer
        transport, protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
        self._writer = asyncio.StreamWriter(transport, protocol, None, loop)
            
        # Send capabilities advertisement
        await self._send_capabilities()
        
        # Process incoming messages
        while True:
            try:
                msg = await self._read_message()
                if not msg:
                    break
                    
                await self._handle_message(msg)
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await self._send_error(str(e))
                
    async def _read_message(self) -> Optional[Dict]:
        """Read and parse a JSON message from stdin."""
        try:
            line = await self._reader.readline()
            if not line:
                return None
                
            return json.loads(line)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
            await self._send_error("Invalid JSON message")
            return None
            
    async def _send_message(self, msg: Dict):
        """Send a JSON message to stdout."""
        try:
            line = json.dumps(msg) + '\n'
            self._writer.write(line.encode())
            await self._writer.drain()
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            
    async def _send_capabilities(self):
        """Send capabilities advertisement message."""
        capabilities = {
            "jsonrpc": "2.0",
            "method": "capabilities",
            "params": {
                "protocol": "1.0.0",
                "name": "terminal",
                "version": "1.0.0",
                "capabilities": {
                    "execute": {
                        "description": "Execute a terminal command",
                        "parameters": {
                            "command": {
                                "type": "string",
                                "description": "The command to execute"
                            }
                        },
                        "returns": {
                            "type": "object",
                            "properties": {
                                "exitCode": {"type": "number"},
                                "stdout": {"type": "string"},
                                "stderr": {"type": "string"},
                                "startTime": {"type": "string"},
                                "endTime": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
        
        await self._send_message(capabilities)
        
    async def _send_error(self, message: str, code: int = -32603, id: Optional[str] = None):
        """Send an error message."""
        error = {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message
            }
        }
        if id is not None:
            error["id"] = id
        
        await self._send_message(error)
        
    async def _handle_message(self, msg: Dict):
        """Handle an incoming message."""
        try:
            if msg.get("jsonrpc") != "2.0":
                await self._send_error("Invalid JSON-RPC version", -32600)
                return
                
            method = msg.get("method")
            if not method:
                await self._send_error("Method not found", -32601, msg.get("id"))
                return
                
            if method != "execute":
                await self._send_error(f"Method '{method}' not found", -32601, msg.get("id"))
                return
                
            params = msg.get("params", {})
            command = params.get("command")
            if not command:
                await self._send_error("Missing command parameter", -32602, msg.get("id"))
                return
                
            # Execute the command
            start_time = datetime.now(timezone.utc)
            try:
                result = await self.executor.execute(command)
                end_time = datetime.now(timezone.utc)
                
                # Send the result
                if result.exit_code == 126:  # Command not allowed
                    await self._send_error(result.stderr, -32000, msg.get("id"))
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg.get("id"),
                        "result": {
                            "command": command,
                            "exitCode": result.exit_code,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "startTime": start_time.isoformat(),
                            "endTime": end_time.isoformat()
                        }
                    }
                    await self._send_message(response)
                    
            except ValueError as e:
                await self._send_error(str(e), -32000, msg.get("id"))
            except asyncio.TimeoutError:
                await self._send_error(
                    f"Command execution timed out after {self.executor.timeout_ms}ms",
                    -32000,
                    msg.get("id")
                )
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            await self._send_error(str(e), -32603, msg.get("id"))
            
def main():
    """Main entry point for the MCP Terminal Server."""
    parser = ArgumentParser(description="MCP Terminal Server")
    parser.add_argument("--allowed-commands", type=str,
                       help="Comma-separated list of allowed commands")
    parser.add_argument("--timeout-ms", type=int, default=30000,
                       help="Maximum execution time in milliseconds")
    parser.add_argument("--max-output-size", type=int, default=1024*1024,
                       help="Maximum output size in bytes")
                       
    args = parser.parse_args()
    
    allowed_commands = set(args.allowed_commands.split(",")) if args.allowed_commands else None
    
    server = MCPTerminalServer(
        allowed_commands=allowed_commands,
        timeout_ms=args.timeout_ms,
        max_output_size=args.max_output_size
    )
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()