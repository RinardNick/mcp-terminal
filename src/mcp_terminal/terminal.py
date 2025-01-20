"""Terminal execution module for MCP Terminal Server"""

from typing import Dict, Any, Optional, List, Tuple, AsyncIterator
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
        
    def _validate_command(self, command: str) -> bool:
        """Validate if a command is allowed to execute
        
        Args:
            command: The command to validate
            
        Returns:
            bool: True if command is allowed, False otherwise
        """
        if not self.allowed_commands:
            return True
            
        try:
            # Split command into parts
            parts = shlex.split(command)
            if not parts:
                return False
                
            # Check if base command is allowed
            base_cmd = parts[0]
            
            # Check for shell operators that could be used for command injection
            shell_operators = ["&&", "||", "|", ";", "`"]
            if any(op in command for op in shell_operators):
                return False
                
            return base_cmd in self.allowed_commands
            
        except ValueError:
            # shlex.split can raise ValueError for malformed commands
            return False
        
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
        
        # Validate command
        if not self._validate_command(command):
            return CommandResult(
                command=command,
                exit_code=126,  # Standard shell error code for permission denied
                stdout="",
                stderr="command not allowed",
                start_time=start_time,
                end_time=datetime.now()
            )
        
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
        
    async def execute_stream(self, command: str) -> AsyncIterator[Dict[str, str]]:
        """Execute a command and stream its output
        
        Args:
            command: The command to execute
            
        Yields:
            dict: Output chunks with either stdout or stderr keys
            
        Raises:
            asyncio.TimeoutError: If command execution exceeds timeout
            ValueError: If command is not allowed or invalid
        """
        # Validate command
        if not self._validate_command(command):
            yield {"stderr": "command not allowed"}
            return
            
        try:
            # Create subprocess with shell
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Start timeout timer
            start_time = asyncio.get_event_loop().time()
            
            # Read output streams concurrently
            total_size = 0
            stdout_done = False
            stderr_done = False
            
            while not (stdout_done and stderr_done):
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > self.timeout_ms / 1000:
                    process.kill()
                    raise asyncio.TimeoutError("Command execution timed out")
                    
                # Read from stdout
                if not stdout_done:
                    try:
                        stdout_chunk = await asyncio.wait_for(
                            process.stdout.read(1024),
                            timeout=0.1  # Short timeout for each read
                        )
                        if stdout_chunk:
                            chunk = stdout_chunk.decode('utf-8')
                            total_size += len(chunk)
                            if total_size > self.max_output_size:
                                process.kill()
                                yield {"stderr": f"Output size exceeded {self.max_output_size} bytes"}
                                return
                            yield {"stdout": chunk}
                        else:
                            stdout_done = True
                    except asyncio.TimeoutError:
                        # Read timeout is ok, just continue
                        pass
                    except Exception:
                        stdout_done = True
                    
                # Read from stderr
                if not stderr_done:
                    try:
                        stderr_chunk = await asyncio.wait_for(
                            process.stderr.read(1024),
                            timeout=0.1  # Short timeout for each read
                        )
                        if stderr_chunk:
                            chunk = stderr_chunk.decode('utf-8')
                            total_size += len(chunk)
                            if total_size > self.max_output_size:
                                process.kill()
                                yield {"stderr": f"Output size exceeded {self.max_output_size} bytes"}
                                return
                            yield {"stderr": chunk}
                        else:
                            stderr_done = True
                    except asyncio.TimeoutError:
                        # Read timeout is ok, just continue
                        pass
                    except Exception:
                        stderr_done = True
                    
                # Check if process has finished
                try:
                    await asyncio.wait_for(process.wait(), timeout=0.1)
                    if not stdout_done or not stderr_done:
                        # Process finished but we haven't read all output
                        continue
                    break
                except asyncio.TimeoutError:
                    # Process still running
                    pass
                
        except asyncio.TimeoutError:
            process.kill()
            raise
        except Exception as e:
            if not isinstance(e, asyncio.TimeoutError):
                yield {"stderr": str(e)}
            raise 