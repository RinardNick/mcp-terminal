"""MCP Terminal Server - A secure terminal execution server.

This module provides a simple and secure way to execute terminal commands with proper
controls and error handling.
"""

from typing import Any
import asyncio
import shlex
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("terminal")

# Constants
DEFAULT_TIMEOUT_MS = 30000  # 30 seconds
DEFAULT_MAX_OUTPUT = 1024 * 1024  # 1MB

async def execute_command(command: str, 
                        allowed_commands: list[str] | None = None,
                        timeout_ms: int = DEFAULT_TIMEOUT_MS,
                        max_output_size: int = DEFAULT_MAX_OUTPUT) -> dict[str, Any]:
    """Execute a terminal command with security controls and return the result."""
    start_time = datetime.now()
    
    try:
        # Validate command if allowed_commands is specified
        if allowed_commands:
            # Split command into parts
            parts = shlex.split(command)
            if not parts:
                raise ValueError("Empty command")
                
            # Check if base command is allowed
            base_cmd = parts[0]
            
            # Check for shell operators that could be used for command injection
            shell_operators = ["&&", "||", "|", ";", "`"]
            if any(op in command for op in shell_operators):
                raise ValueError("Shell operators not allowed")
                
            if base_cmd not in allowed_commands:
                raise ValueError(f"Command '{base_cmd}' not allowed")
        
        # Create subprocess
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            # Wait for process with timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_ms / 1000
            )
            
            # Check output size
            total_size = len(stdout_bytes) + len(stderr_bytes)
            if total_size > max_output_size:
                process.kill()
                raise ValueError(f"Output size exceeded {max_output_size} bytes")
            
            return {
                "exitCode": process.returncode or 0,
                "stdout": stdout_bytes.decode('utf-8'),
                "stderr": stderr_bytes.decode('utf-8'),
                "startTime": start_time.isoformat(),
                "endTime": datetime.now().isoformat()
            }
            
        except asyncio.TimeoutError:
            process.kill()
            raise asyncio.TimeoutError(f"Command execution timed out after {timeout_ms}ms")
            
    except FileNotFoundError:
        return {
            "exitCode": 127,
            "stdout": "",
            "stderr": "command not found",
            "startTime": start_time.isoformat(),
            "endTime": datetime.now().isoformat()
        }
    except ValueError as e:
        return {
            "exitCode": 126,
            "stdout": "",
            "stderr": str(e),
            "startTime": start_time.isoformat(),
            "endTime": datetime.now().isoformat()
        }

@mcp.tool()
async def run_command(command: str, 
              allowed_commands: list[str] | None = None,
              timeout_ms: int = DEFAULT_TIMEOUT_MS,
              max_output_size: int = DEFAULT_MAX_OUTPUT) -> dict[str, Any]:
    """Run a terminal command with security controls.
    
    Args:
        command: The command to execute
        allowed_commands: Optional list of allowed command executables
        timeout_ms: Maximum execution time in milliseconds (default: 30 seconds)
        max_output_size: Maximum output size in bytes (default: 1MB)
    """
    return await execute_command(
        command=command,
        allowed_commands=allowed_commands,
        timeout_ms=timeout_ms,
        max_output_size=max_output_size
    )

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')