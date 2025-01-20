# MCP Terminal Server

A secure terminal execution server implementing the Model Context Protocol (MCP). This server provides controlled command execution capabilities with security features and resource limits.

## Features

- **Command Execution**: Execute shell commands with output capture and error handling
- **Security Controls**: Restrict allowed commands and prevent command injection
- **Resource Controls**:
  - Command timeouts
  - Maximum output size limits
- **MCP Protocol Support**:
  - Standard MCP message format
  - Capability advertisement
  - Streaming output support

## Installation

```bash
# Install from npm (for use with Claude Desktop)
npm install -g @rinardnick/mcp-terminal

# Install for development
git clone https://github.com/RinardNick/mcp-terminal.git
cd mcp-terminal
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Using with Claude Desktop

1. **Install the Module**:

   ```bash
   npm install -g @rinardnick/mcp-terminal
   ```

2. **Configure Claude Desktop**:
   Edit your Claude Desktop config file (typically at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

   ```json
   {
     "servers": {
       "terminal": {
         "command": "python3",
         "args": [
           "-m",
           "mcp_terminal.server",
           "--allowed-commands",
           "python,pip,git,ls,cd",
           "--timeout-ms",
           "30000",
           "--max-output-size",
           "1048576"
         ]
       }
     }
   }
   ```

## Development

### Testing with MCP Inspector

The MCP Inspector tool can be used to test the server implementation:

```bash
# Install inspector
npm install -g @modelcontextprotocol/inspector

# Test server
npx @modelcontextprotocol/inspector python3 src/mcp_terminal/server.py --allowed-commands "python,pip,git,ls,cd"
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_terminal.py

# Run with coverage
pytest --cov=mcp_terminal tests/
```

## Protocol Implementation

The server implements the Model Context Protocol (MCP) with the following capabilities:

### Capabilities Advertisement

```json
{
  "protocol": "1.0.0",
  "name": "terminal",
  "version": "1.1.0",
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
          "exitCode": { "type": "number" },
          "stdout": { "type": "string" },
          "stderr": { "type": "string" },
          "startTime": { "type": "string" },
          "endTime": { "type": "string" }
        }
      }
    }
  }
}
```

### Message Format

**Request**:

```json
{
  "type": "execute",
  "data": {
    "command": "echo 'hello world'"
  }
}
```

**Response**:

```json
{
  "type": "result",
  "data": {
    "command": "echo 'hello world'",
    "exitCode": 0,
    "stdout": "hello world\n",
    "stderr": "",
    "startTime": "2024-01-20T12:34:56.789Z",
    "endTime": "2024-01-20T12:34:56.790Z"
  }
}
```

**Error**:

```json
{
  "type": "error",
  "data": {
    "message": "command not allowed"
  }
}
```

## Security Considerations

1. **Command Validation**:

   - Only allowed commands can be executed
   - Shell operators are blocked
   - Command injection attempts are prevented

2. **Resource Protection**:

   - Command timeouts prevent hanging
   - Output size limits prevent memory exhaustion
   - Error handling for all failure cases

3. **Best Practices**:
   - Always set `allowed-commands` in production
   - Use conservative timeout and size limits
   - Monitor command execution logs

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
