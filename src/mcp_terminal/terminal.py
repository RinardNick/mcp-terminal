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