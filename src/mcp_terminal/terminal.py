"""Terminal execution module for MCP Terminal Server"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import asyncio
import shlex
import logging
from datetime import datetime

@dataclass
class CommandResult:
    """Result of a command execution"""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    start_time: datetime
    end_time: datetime
    
    @property
    def duration_ms(self) -> float:
        """Get command execution duration in milliseconds"""
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format"""
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat()
        }

class TerminalExecutor:
    """Terminal command execution handler"""
    
    def __init__(self, 
                 allowed_commands: Optional[List[str]] = None,
                 timeout_ms: int = 30000,
                 max_output_size: int = 1024 * 1024):  # 1MB default
        self.allowed_commands = allowed_commands
        self.timeout_ms = timeout_ms
        self.max_output_size = max_output_size
        self.logger = logging.getLogger(__name__)
        
    async def execute(self, command: str) -> CommandResult:
        """Execute a command and return its result
        
        Args:
            command: The command to execute
            
        Returns:
            CommandResult: The result of command execution
            
        Raises:
            asyncio.TimeoutError: If command execution exceeds timeout
            ValueError: If command is not allowed or invalid
        """
        start_time = datetime.now()
        
        try:
            # Create subprocess with shell
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # Wait for process with timeout
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_ms / 1000  # Convert to seconds
                )
                
                # Decode output
                stdout = stdout_bytes.decode('utf-8')
                stderr = stderr_bytes.decode('utf-8')
                
                # Check output size
                total_size = len(stdout) + len(stderr)
                if total_size > self.max_output_size:
                    process.kill()
                    raise ValueError(f"Command output exceeds maximum size of {self.max_output_size} bytes")
                
            except asyncio.TimeoutError:
                process.kill()
                raise
                
        except FileNotFoundError:
            self.logger.error(f"Command not found: {command}")
            return CommandResult(
                command=command,
                exit_code=127,  # Standard shell error code for command not found
                stdout="",
                stderr="command not found",
                start_time=start_time,
                end_time=datetime.now()
            )
        except Exception as e:
            if not isinstance(e, asyncio.TimeoutError):
                self.logger.error(f"Command execution failed: {str(e)}")
                # For non-timeout errors, return a result with the error
                return CommandResult(
                    command=command,
                    exit_code=-1,
                    stdout="",
                    stderr=str(e),
                    start_time=start_time,
                    end_time=datetime.now()
                )
            raise
            
        return CommandResult(
            command=command,
            exit_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
            start_time=start_time,
            end_time=datetime.now()
        ) 