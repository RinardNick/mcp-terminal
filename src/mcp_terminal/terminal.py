"""Terminal execution module for MCP Terminal Server.

This module provides a secure and feature-rich way to execute terminal commands with advanced control
and monitoring capabilities. It supports:

- Command execution with output capture and error handling
- Security controls with allowed command lists and command injection prevention
- Resource monitoring (CPU time, memory usage, process count)
- Output control (size limits, timeouts, streaming)
- Comprehensive error handling and status reporting

Example:
    ```python
    import asyncio
    from mcp_terminal.terminal import TerminalExecutor

    async def main():
        # Create executor with resource limits
        executor = TerminalExecutor(
            allowed_commands=["echo", "ls"],
            cpu_time_ms=1000,
            max_memory_mb=100,
            max_processes=5
        )

        try:
            # Execute command
            result = await executor.execute("echo 'test'")
            print(f"Output: {result.stdout}")
            print(f"Exit code: {result.exit_code}")

            # Stream command output
            async for chunk in executor.execute_stream("ls -l"):
                if "stdout" in chunk:
                    print(chunk["stdout"], end="")
        except ValueError as e:
            print(f"Resource limit exceeded: {e}")
        except asyncio.TimeoutError:
            print("Command timed out")

    asyncio.run(main())
    ```
"""

from typing import Dict, Any, Optional, List, Tuple, AsyncIterator
from dataclasses import dataclass
import asyncio
import shlex
import logging
import psutil
import signal
from datetime import datetime

@dataclass
class CommandResult:
    """Result of a command execution.
    
    This class encapsulates all information about a command's execution, including
    its output, exit code, and timing information.
    
    Attributes:
        command (str): The command that was executed
        exit_code (int): The command's exit code (0 for success)
        stdout (str): Standard output from the command
        stderr (str): Standard error from the command
        start_time (datetime): When command execution started
        end_time (datetime): When command execution completed
        
    Properties:
        duration_ms (float): Command execution duration in milliseconds
        
    Example:
        ```python
        result = await executor.execute("echo 'test'")
        if result.exit_code == 0:
            print(f"Success! Output: {result.stdout}")
        else:
            print(f"Failed! Error: {result.stderr}")
        print(f"Took {result.duration_ms}ms")
        ```
    """
    command: str
    exit_code: int
    stdout: str
    stderr: str
    start_time: datetime
    end_time: datetime
    
    @property
    def duration_ms(self) -> float:
        """Get command execution duration in milliseconds."""
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format.
        
        Returns:
            dict: Dictionary containing all result fields
        """
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
    """Terminal command execution handler with security and resource controls.
    
    This class provides a secure way to execute terminal commands with various
    controls and limits:
    
    - Command validation and security controls
    - Resource monitoring (CPU, memory, processes)
    - Output size limits
    - Command timeouts
    - Output streaming support
    
    Example:
        ```python
        # Create executor with limits
        executor = TerminalExecutor(
            allowed_commands=["echo", "ls"],
            timeout_ms=5000,
            max_output_size=1024 * 1024,
            cpu_time_ms=1000,
            max_memory_mb=100,
            max_processes=5
        )
        
        # Execute command
        result = await executor.execute("echo 'test'")
        
        # Stream command output
        async for chunk in executor.execute_stream("ls -l"):
            print(chunk.get("stdout", ""), end="")
        ```
    """
    
    def __init__(self, 
                 allowed_commands: Optional[List[str]] = None,
                 timeout_ms: int = 30000,
                 max_output_size: int = 1024 * 1024,  # 1MB default
                 cpu_time_ms: Optional[int] = None,
                 max_memory_mb: Optional[int] = None,
                 max_processes: Optional[int] = None):
        """Initialize terminal executor.
        
        Args:
            allowed_commands: List of allowed command executables. If None, all commands are allowed.
            timeout_ms: Maximum execution time in milliseconds (default: 30 seconds)
            max_output_size: Maximum combined stdout/stderr size in bytes (default: 1MB)
            cpu_time_ms: Maximum CPU time in milliseconds (optional)
            max_memory_mb: Maximum memory usage in megabytes (optional)
            max_processes: Maximum number of processes (optional)
            
        Example:
            ```python
            # Allow only safe commands with resource limits
            executor = TerminalExecutor(
                allowed_commands=["echo", "ls"],
                timeout_ms=5000,
                max_output_size=1024 * 1024,  # 1MB
                cpu_time_ms=1000,             # 1 second
                max_memory_mb=100,            # 100MB
                max_processes=5
            )
            ```
        """
        self.allowed_commands = allowed_commands
        self.timeout_ms = timeout_ms
        self.max_output_size = max_output_size
        self.cpu_time_ms = cpu_time_ms
        self.max_memory_mb = max_memory_mb
        self.max_processes = max_processes
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

    async def _monitor_process(self, process: asyncio.subprocess.Process) -> None:
        """Monitor process resource usage
        
        Args:
            process: The process to monitor
            
        Raises:
            ValueError: If resource limits are exceeded
        """
        try:
            proc = psutil.Process(process.pid)
            start_time = datetime.now()
            
            while process.returncode is None:
                try:
                    # Check CPU time
                    if self.cpu_time_ms:
                        cpu_time = proc.cpu_times()
                        total_cpu_ms = (cpu_time.user + cpu_time.system) * 1000
                        if total_cpu_ms > self.cpu_time_ms:
                            process.kill()
                            raise ValueError("CPU time limit exceeded")
                    
                    # Check memory usage
                    if self.max_memory_mb:
                        memory_mb = proc.memory_info().rss / (1024 * 1024)
                        if memory_mb > self.max_memory_mb:
                            process.kill()
                            raise ValueError("Memory limit exceeded")
                    
                    # Check process count (including all descendants)
                    if self.max_processes:
                        try:
                            # Get all descendant processes recursively
                            children = proc.children(recursive=True)
                            total_processes = len(children) + 1  # +1 for the main process
                            
                            # Kill all processes if limit exceeded
                            if total_processes > self.max_processes:
                                for child in children:
                                    try:
                                        child.kill()
                                    except psutil.NoSuchProcess:
                                        pass
                                process.kill()
                                raise ValueError("Process limit exceeded")
                                
                        except psutil.NoSuchProcess:
                            # Process or child disappeared, which is fine
                            pass
                    
                    await asyncio.sleep(0.05)  # Check more frequently (50ms)
                    
                except psutil.NoSuchProcess:
                    # Main process disappeared
                    break
                    
        except psutil.NoSuchProcess:
            # Process already terminated
            pass

    async def execute(self, command: str) -> CommandResult:
        """Execute a command and return its result
        
        Args:
            command: The command to execute
            
        Returns:
            CommandResult: The result of command execution
            
        Raises:
            asyncio.TimeoutError: If command execution exceeds timeout
            ValueError: If command is not allowed, invalid, or exceeds resource limits
        """
        start_time = datetime.now()
        
        # Validate command
        if not self._validate_command(command):
            return CommandResult(
                command=command,
                exit_code=126,
                stdout="",
                stderr="command not allowed",
                start_time=start_time,
                end_time=datetime.now()
            )
        
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Start resource monitoring
            monitor_task = asyncio.create_task(self._monitor_process(process))
            
            try:
                # Wait for process with timeout
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_ms / 1000
                )
                
                # Cancel monitoring
                monitor_task.cancel()
                try:
                    await monitor_task
                except (asyncio.CancelledError, ValueError) as e:
                    # If monitoring task was cancelled due to a resource limit,
                    # we need to re-raise the ValueError
                    if isinstance(e, ValueError):
                        raise
                
                # Decode output
                stdout = stdout_bytes.decode('utf-8')
                stderr = stderr_bytes.decode('utf-8')
                
                # Check output size
                total_size = len(stdout) + len(stderr)
                if total_size > self.max_output_size:
                    process.kill()
                    raise ValueError(f"Command output exceeds maximum size of {self.max_output_size} bytes")
                
            except asyncio.TimeoutError:
                monitor_task.cancel()
                process.kill()
                raise
                
        except FileNotFoundError:
            self.logger.error(f"Command not found: {command}")
            return CommandResult(
                command=command,
                exit_code=127,
                stdout="",
                stderr="command not found",
                start_time=start_time,
                end_time=datetime.now()
            )
        except Exception as e:
            if isinstance(e, (asyncio.TimeoutError, ValueError)):
                # Re-raise timeout and resource limit errors
                raise
            self.logger.error(f"Command execution failed: {str(e)}")
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                start_time=start_time,
                end_time=datetime.now()
            )
            
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