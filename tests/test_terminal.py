"""Tests for terminal execution functionality"""

import pytest
import asyncio
from datetime import datetime, timedelta
from mcp_terminal.terminal import TerminalExecutor, CommandResult

@pytest.mark.asyncio
async def test_basic_command_execution():
    """Test basic command execution functionality"""
    executor = TerminalExecutor()
    
    # Test simple echo command
    result = await executor.execute("echo 'hello world'")
    assert isinstance(result, CommandResult)
    assert result.command == "echo 'hello world'"
    assert result.exit_code == 0
    assert "hello world" in result.stdout
    assert result.stderr == ""
    assert isinstance(result.start_time, datetime)
    assert isinstance(result.end_time, datetime)
    assert result.duration_ms > 0

@pytest.mark.asyncio
async def test_command_output_capture():
    """Test command output capture functionality"""
    executor = TerminalExecutor()
    
    # Test stdout
    result = await executor.execute("echo 'test stdout'")
    assert result.stdout.strip() == "test stdout"
    assert result.stderr == ""
    
    # Test stderr
    result = await executor.execute("echo 'test stderr' >&2")
    assert result.stdout == ""
    assert result.stderr.strip() == "test stderr"
    
    # Test both stdout and stderr
    result = await executor.execute("echo 'out' && echo 'err' >&2")
    assert result.stdout.strip() == "out"
    assert result.stderr.strip() == "err"

@pytest.mark.asyncio
async def test_command_timeout():
    """Test command timeout functionality"""
    executor = TerminalExecutor(timeout_ms=100)  # 100ms timeout
    
    # Test command that exceeds timeout
    with pytest.raises(asyncio.TimeoutError):
        await executor.execute("sleep 1")  # Should timeout after 100ms

@pytest.mark.asyncio
async def test_execution_errors():
    """Test handling of command execution errors"""
    executor = TerminalExecutor()
    
    # Test non-existent command
    result = await executor.execute("nonexistentcommand")
    assert result.exit_code != 0
    assert "command not found" in result.stderr.lower()
    
    # Test command that returns error
    result = await executor.execute("exit 1")
    assert result.exit_code == 1

@pytest.mark.asyncio
async def test_command_validation():
    """Test command validation and security controls"""
    # Test with allowed commands
    executor = TerminalExecutor(allowed_commands=["echo", "ls"])
    
    # Test allowed command
    result = await executor.execute("echo 'test'")
    assert result.exit_code == 0
    
    # Test command with arguments
    result = await executor.execute("echo 'test' 'arg2'")
    assert result.exit_code == 0
    
    # Test disallowed command
    result = await executor.execute("cat /etc/passwd")
    assert result.exit_code == 126
    assert "Command validation failed: Command 'cat' not allowed" in result.stderr
    
    # Test command injection attempt
    result = await executor.execute("echo 'test' && ls")
    assert result.exit_code == 126
    assert "Shell operators not allowed" in result.stderr
    
    # Test with no restrictions
    executor = TerminalExecutor()  # No allowed_commands means all commands allowed
    result = await executor.execute("echo 'test' && ls")
    assert result.exit_code == 0

@pytest.mark.asyncio
async def test_command_streaming():
    """Test streaming output from commands"""
    executor = TerminalExecutor()
    
    chunks = []
    async for chunk in executor.execute_stream("for i in {1..3}; do echo $i; sleep 0.1; done"):
        chunks.append(chunk)
        
    # Should have at least 3 output chunks
    assert len([c for c in chunks if "stdout" in c]) >= 3
    
    # Verify output content
    stdout = "".join(c["stdout"] for c in chunks if "stdout" in c)
    assert "1\n2\n3\n" in stdout

# Note: Resource limits test removed as it was flaky and the functionality
# was removed from the implementation 