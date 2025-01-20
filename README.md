# MCP Terminal Execution Module

A secure and feature-rich Python module for executing terminal commands with advanced control and monitoring capabilities.

## Features

- **Command Execution**: Execute shell commands with output capture and error handling
- **Security Controls**: Restrict allowed commands and prevent command injection
- **Resource Monitoring**:
  - CPU time limits
  - Memory usage limits
  - Process count limits
- **Output Control**:
  - Maximum output size limits
  - Command timeouts
  - Streaming output support
- **Error Handling**: Comprehensive error handling and status reporting

## Installation

```bash
npm install -g @rinardnick/mcp-terminal
```

## Using with Claude Desktop

The MCP Terminal module can be integrated with Claude Desktop as a server plugin. Here's how to set it up:

1. **Install the Module**:

   ```bash
   npm install -g @rinardnick/mcp-terminal
   ```

2. **Configure Claude Desktop**:
   Edit your Claude Desktop config file (typically located at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS) and add the terminal server configuration:

   ```json
   {
     "servers": {
       "terminal": {
         "command": "npx",
         "args": [
           "-y",
           "@rinardnick/mcp-terminal",
           "--allowed-commands",
           "python,pip,git,ls,cd",
           "--timeout-ms",
           "30000",
           "--max-memory-mb",
           "500",
           "--max-processes",
           "10"
         ]
       }
     }
   }
   ```

   Available configuration options:

   - `--allowed-commands`: Comma-separated list of allowed commands
   - `--timeout-ms`: Maximum execution time in milliseconds (default: 30000)
   - `--max-memory-mb`: Maximum memory usage in megabytes (optional)
   - `--max-processes`: Maximum number of processes (optional)
   - `--max-output-size`: Maximum output size in bytes (default: 1MB)
   - `--log-file`: Path to log file for execution logging (optional)

3. **Security Recommendations**:

   - Always set `allowed-commands` to restrict which commands Claude can execute
   - Use conservative resource limits
   - Consider enabling logging to monitor command execution
   - Regularly review the logs for suspicious activity

4. **Verification**:
   After configuring, Claude Desktop will automatically use the MCP Terminal server for command execution. You can verify it's working by:
   - Checking Claude Desktop's logs for successful server initialization
   - Running a simple command like `ls` in Claude
   - Verifying that disallowed commands are blocked

## Publishing

To publish this package to npm:

1. Create an npm account if you don't have one
2. Login to npm:
   ```bash
   npm login
   ```
3. Publish the package:
   ```bash
   npm publish --access public
   ```

Note: Make sure to create the GitHub repository at `https://github.com/RinardNick/mcp-terminal` before publishing.

## Using as a Standalone Module

If you want to use the terminal execution functionality in your own Python code:

```python
import asyncio
from mcp_terminal.terminal import TerminalExecutor

async def main():
    # Create executor with default settings
    executor = TerminalExecutor()

    # Execute a simple command
    result = await executor.execute("echo 'Hello, World!'")
    print(f"Output: {result.stdout}")
    print(f"Exit code: {result.exit_code}")

    # Stream command output
    async for chunk in executor.execute_stream("for i in 1 2 3; do echo $i; sleep 1; done"):
        if "stdout" in chunk:
            print(f"Output: {chunk['stdout']}", end="")
        elif "stderr" in chunk:
            print(f"Error: {chunk['stderr']}", end="")

if __name__ == "__main__":
    asyncio.run(main())
```

## Usage Examples

### Basic Command Execution

```python
executor = TerminalExecutor()
result = await executor.execute("ls -l")
print(result.stdout)
```

### Security Controls

```python
# Only allow specific commands
executor = TerminalExecutor(allowed_commands=["echo", "ls"])

# This will succeed
result = await executor.execute("echo 'test'")

# This will fail with "command not allowed"
result = await executor.execute("rm -rf /")
```

### Resource Limits

```python
executor = TerminalExecutor(
    cpu_time_ms=1000,      # 1 second CPU time limit
    max_memory_mb=100,     # 100MB memory limit
    max_processes=5,       # Maximum 5 processes
    timeout_ms=5000,       # 5 second timeout
    max_output_size=10240  # 10KB output limit
)

try:
    result = await executor.execute("resource_intensive_command")
except ValueError as e:
    print(f"Resource limit exceeded: {e}")
except asyncio.TimeoutError:
    print("Command timed out")
```

### Output Streaming

```python
async for chunk in executor.execute_stream("long_running_command"):
    if "stdout" in chunk:
        print(f"Output: {chunk['stdout']}", end="")
    elif "stderr" in chunk:
        print(f"Error: {chunk['stderr']}", end="")
```

## API Reference

### TerminalExecutor

```python
class TerminalExecutor:
    def __init__(self,
                 allowed_commands: Optional[List[str]] = None,
                 timeout_ms: int = 30000,
                 max_output_size: int = 1024 * 1024,
                 cpu_time_ms: Optional[int] = None,
                 max_memory_mb: Optional[int] = None,
                 max_processes: Optional[int] = None)
```

#### Parameters

- `allowed_commands`: List of allowed command executables. If None, all commands are allowed.
- `timeout_ms`: Maximum execution time in milliseconds (default: 30 seconds).
- `max_output_size`: Maximum combined stdout/stderr size in bytes (default: 1MB).
- `cpu_time_ms`: Maximum CPU time in milliseconds (optional).
- `max_memory_mb`: Maximum memory usage in megabytes (optional).
- `max_processes`: Maximum number of processes (optional).

#### Methods

```python
async def execute(self, command: str) -> CommandResult
```

Execute a command and return its result.

- **Parameters**:
  - `command`: The command to execute
- **Returns**: `CommandResult` object
- **Raises**:
  - `asyncio.TimeoutError`: If command execution exceeds timeout
  - `ValueError`: If command is not allowed or resource limits are exceeded

```python
async def execute_stream(self, command: str) -> AsyncIterator[Dict[str, str]]
```

Execute a command and stream its output.

- **Parameters**:
  - `command`: The command to execute
- **Yields**: Dictionaries with either "stdout" or "stderr" keys
- **Raises**:
  - `asyncio.TimeoutError`: If command execution exceeds timeout
  - `ValueError`: If command is not allowed

### CommandResult

```python
@dataclass
class CommandResult:
    command: str          # The executed command
    exit_code: int       # Command exit code
    stdout: str          # Standard output
    stderr: str          # Standard error
    start_time: datetime # Execution start time
    end_time: datetime   # Execution end time

    @property
    def duration_ms(self) -> float:
        """Get command execution duration in milliseconds"""
```

## Error Handling

The module uses the following error codes:

- Exit code 126: Command not allowed
- Exit code 127: Command not found
- Exit code -1: General execution error

Resource limit violations raise `ValueError` with descriptive messages:

- "CPU time limit exceeded"
- "Memory limit exceeded"
- "Process limit exceeded"
- "Command output exceeds maximum size"

Command timeouts raise `asyncio.TimeoutError`.

## Security Considerations

1. **Command Injection Prevention**:

   - Commands are validated against an allowed list
   - Shell operators are blocked when using allowed commands
   - Command arguments are properly escaped

2. **Resource Protection**:

   - CPU time limits prevent infinite loops
   - Memory limits prevent memory exhaustion
   - Process limits prevent fork bombs
   - Output limits prevent disk space exhaustion

3. **Timeouts**:
   - All operations have timeouts
   - Long-running commands can be interrupted
   - Streaming operations have chunk timeouts

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
