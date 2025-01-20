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
    assert result.exit_code != 0
    assert "command not allowed" in result.stderr.lower()
    
    # Test command injection attempt
    result = await executor.execute("echo 'test' && cat /etc/passwd")
    assert result.exit_code != 0
    assert "command not allowed" in result.stderr.lower()
    
    # Test with no restrictions
    executor = TerminalExecutor()  # No allowed_commands means all commands allowed
    result = await executor.execute("echo 'test' && ls")
    assert result.exit_code == 0

@pytest.mark.asyncio
async def test_command_streaming():
    """Test command output streaming"""
    executor = TerminalExecutor()
    
    # Test basic streaming
    chunks = []
    async for chunk in executor.execute_stream("for i in 1 2 3; do echo $i; sleep 0.1; done"):
        chunks.append(chunk)
    
    # Combine all stdout chunks
    stdout = "".join(c["stdout"] for c in chunks if "stdout" in c)
    assert "1" in stdout
    assert "2" in stdout
    assert "3" in stdout
    assert len(chunks) > 0  # Should get at least one chunk
    
    # Test error streaming
    chunks = []
    async for chunk in executor.execute_stream("echo 'error' >&2"):
        chunks.append(chunk)
    
    stderr = "".join(c["stderr"] for c in chunks if "stderr" in c)
    assert "error" in stderr
    
    # Test timeout during streaming
    executor = TerminalExecutor(timeout_ms=100)
    with pytest.raises(asyncio.TimeoutError):
        async for _ in executor.execute_stream("sleep 1"):
            pass

@pytest.mark.asyncio
async def test_resource_limits():
    """Test resource limits for command execution"""
    # Test CPU time limit
    executor = TerminalExecutor(cpu_time_ms=100)  # 100ms CPU time limit
    with pytest.raises(ValueError) as exc_info:
        await executor.execute("python3 -c 'while True: pass'")  # CPU-intensive loop
    assert "CPU time limit exceeded" in str(exc_info.value)
    
    # Test memory limit
    executor = TerminalExecutor(max_memory_mb=10)  # 10MB memory limit
    with pytest.raises(ValueError) as exc_info:
        # Try to allocate more memory than allowed
        await executor.execute("python3 -c 'x = [0] * 1000000000'")
    assert "Memory limit exceeded" in str(exc_info.value)
    
    # Test process limit
    executor = TerminalExecutor(max_processes=1)  # Only allow 1 subprocess
    with pytest.raises(ValueError) as exc_info:
        # Try to spawn multiple processes using a bash script
        await executor.execute("""bash -c '
            python3 -c "import time; time.sleep(10)" &
            python3 -c "import time; time.sleep(10)" &
            wait
        '""")
    assert "Process limit exceeded" in str(exc_info.value)
    
    # Test combined limits
    executor = TerminalExecutor(
        cpu_time_ms=1000,
        max_memory_mb=50,
        max_processes=2
    )
    # Test command within limits should succeed
    result = await executor.execute("echo 'test'")
    assert result.exit_code == 0 