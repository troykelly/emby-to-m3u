"""Claude JSON log interpreter with Rich terminal output."""

import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Generator, TextIO
from enum import Enum
from dataclasses import dataclass

from rich.console import Console
from rich.text import Text
from rich.live import Live
from rich.table import Table
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .exceptions import GitHubAutomationError
from .logging_setup import get_logger


class MessageType(Enum):
    """Claude message types."""
    ASSISTANT = "assistant"
    USER = "user"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    UNKNOWN = "unknown"


@dataclass
class ClaudeMessage:
    """Parsed Claude message with security validation."""
    
    message_type: MessageType
    timestamp: str
    session_id: str
    uuid: Optional[str]
    content: str
    tool_name: Optional[str] = None
    is_error: bool = False
    raw_data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate and sanitize message data after initialization."""
        # Sanitize content for display
        self.content = self._sanitize_content(self.content)
        
        # Validate session ID format
        if self.session_id and not self._is_valid_session_id(self.session_id):
            self.session_id = "[INVALID_SESSION_ID]"
        
        # Validate UUID format
        if self.uuid and not self._is_valid_uuid(self.uuid):
            self.uuid = None
        
        # Sanitize tool name
        if self.tool_name:
            self.tool_name = self._sanitize_tool_name(self.tool_name)
    
    def _sanitize_content(self, content: str) -> str:
        """Sanitize content for safe display."""
        if not isinstance(content, str):
            content = str(content)
        
        # Use the security sanitization from our exception system
        # Create a temporary error instance to use its sanitization method
        from ..core.exceptions import GitHubAutomationError
        temp_error = GitHubAutomationError("")
        return temp_error._sanitize_message(content)
    
    def _is_valid_session_id(self, session_id: str) -> bool:
        """Validate session ID format."""
        if not isinstance(session_id, str):
            return False
        # Allow alphanumeric, hyphens, underscores
        return re.match(r'^[a-zA-Z0-9_-]{1,64}$', session_id) is not None
    
    def _is_valid_uuid(self, uuid_str: str) -> bool:
        """Validate UUID format."""
        if not isinstance(uuid_str, str):
            return False
        try:
            uuid.UUID(uuid_str)
            return True
        except ValueError:
            return False
    
    def _sanitize_tool_name(self, tool_name: str) -> str:
        """Sanitize tool name for display."""
        if not isinstance(tool_name, str):
            return str(tool_name)
        # Allow only safe characters
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '', tool_name)
        return clean_name[:50]  # Limit length


class LogInterpreter:
    """Interprets Claude JSON logs with Rich terminal output."""
    
    def __init__(self, console: Optional[Console] = None):
        """
        Initialize log interpreter.
        
        Args:
            console: Optional Rich console instance
        """
        self.console = console or Console()
        self.logger = get_logger(__name__)
        
        # Message type styling
        self.styles = {
            MessageType.ASSISTANT: "cyan",
            MessageType.USER: "green", 
            MessageType.TOOL_USE: "yellow",
            MessageType.TOOL_RESULT: "magenta",
            MessageType.UNKNOWN: "white",
        }
        
        # Icons for message types
        self.icons = {
            MessageType.ASSISTANT: "🔧",
            MessageType.USER: "👤",
            MessageType.TOOL_USE: "⚙️",
            MessageType.TOOL_RESULT: "✅",
            MessageType.UNKNOWN: "❓",
        }
    
    def parse_message(self, line: str) -> Optional[ClaudeMessage]:
        """
        Parse a single JSON log line into a ClaudeMessage securely.
        
        Args:
            line: JSON log line
            
        Returns:
            ClaudeMessage or None if parsing fails
        """
        try:
            # Validate input
            if not isinstance(line, str):
                self.logger.warning(f"Invalid line type: {type(line)}")
                return None
                
            line = line.strip()
            if not line:
                return None
            
            # Limit line length to prevent memory issues
            if len(line) > 100000:  # 100KB limit
                self.logger.warning("Log line too large, truncating")
                line = line[:100000]
            
            # Parse JSON safely
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                self.logger.debug(f"Failed to parse JSON: {e}")
                return None
            
            # Validate data structure
            if not isinstance(data, dict):
                self.logger.warning("Log entry is not a JSON object")
                return None
            
            # Extract and validate basic information safely
            msg_type = self._safe_get_string(data, "type", "unknown")
            session_id = self._safe_get_string(data, "session_id", "unknown")
            uuid_raw = self._safe_get_string(data, "uuid", "")
            uuid_short = uuid_raw[:8] if uuid_raw else None
            timestamp = time.strftime("%H:%M:%S")
            
            # Determine message type safely
            try:
                message_type = MessageType(msg_type)
            except ValueError:
                message_type = MessageType.UNKNOWN
            
            # Extract content based on message type
            content = self._extract_content(data, message_type)
            
            # Extract tool information if applicable
            tool_name = None
            if message_type in (MessageType.TOOL_USE, MessageType.TOOL_RESULT):
                tool_name = self._safe_get_string(data, "name", None)
            
            # Check for error status
            is_error = self._safe_get_bool(data, "is_error", False)
            
            # Create sanitized raw data copy (remove sensitive fields)
            raw_data = self._sanitize_raw_data(data)
            
            return ClaudeMessage(
                message_type=message_type,
                timestamp=timestamp,
                session_id=session_id,
                uuid=uuid_short,
                content=content,
                tool_name=tool_name,
                is_error=is_error,
                raw_data=raw_data
            )
            
        except Exception as e:
            self.logger.debug(f"Failed to parse message: {e}")
            return None
    
    def _safe_get_string(self, data: Dict[str, Any], key: str, default: str = "") -> str:
        """Safely extract string value from dictionary."""
        value = data.get(key, default)
        if not isinstance(value, str):
            return str(value) if value is not None else default
        return value
    
    def _safe_get_bool(self, data: Dict[str, Any], key: str, default: bool = False) -> bool:
        """Safely extract boolean value from dictionary."""
        value = data.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value) if value is not None else default
    
    def _extract_content(self, data: Dict[str, Any], message_type: MessageType) -> str:
        """Extract content based on message type."""
        if message_type == MessageType.ASSISTANT:
            return self._safe_get_string(data, "content", "[No content]")
        elif message_type == MessageType.USER:
            return self._safe_get_string(data, "content", "[No content]")
        elif message_type == MessageType.TOOL_USE:
            input_data = data.get("input", {})
            if isinstance(input_data, dict):
                # Truncate large inputs
                content = str(input_data)
                if len(content) > 500:
                    content = content[:500] + "..."
                return content
            return str(input_data)
        elif message_type == MessageType.TOOL_RESULT:
            content_data = data.get("content", "[No result]")
            content = str(content_data)
            # Truncate large results
            if len(content) > 1000:
                content = content[:1000] + "..."
            return content
        else:
            return self._safe_get_string(data, "content", "[Unknown message type]")
    
    def _sanitize_raw_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create sanitized copy of raw data for storage."""
        if not isinstance(data, dict):
            return {}
        
        # Create a copy and remove/sanitize sensitive fields
        sanitized = {}
        for key, value in data.items():
            if key.lower() in ('password', 'token', 'secret', 'api_key', 'auth'):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate very long strings
                sanitized[key] = value[:1000] + "..."
            else:
                sanitized[key] = value
        
        return sanitized
    
    def format_message(self, message: ClaudeMessage, compact: bool = False) -> Text:
        """
        Format a Claude message for Rich console display.
        
        Args:
            message: ClaudeMessage to format
            compact: Use compact single-line format
            
        Returns:
            Rich Text object
        """
        style = self.styles.get(message.message_type, "white")
        icon = self.icons.get(message.message_type, "❓")
        
        if message.is_error:
            icon = "❌"
            style = "red"
        
        if compact:
            # Single line format
            text = Text()
            text.append(f"[{message.timestamp}] ", style="dim")
            text.append(f"{icon} ", style=style)
            text.append(message.content, style=style)
            return text
        else:
            # Multi-line format with box
            text = Text()
            text.append(f"┌─ [{message.timestamp}] ", style=style)
            text.append(message.message_type.value.upper(), style=f"bold {style}")
            text.append("\n")
            text.append(f"│  Session: {message.session_id}", style=style)
            text.append("\n")
            if message.uuid:
                text.append(f"│  UUID: {message.uuid}", style=style)
                text.append("\n")
            text.append(f"│  {icon} {message.content}", style=style)
            text.append("\n")
            text.append(f"└─", style=style)
            return text
    
    def _should_display(
        self, 
        message: ClaudeMessage, 
        filter_type: Optional[str] = None,
        session_filter: Optional[str] = None
    ) -> bool:
        """Check if message should be displayed based on filters."""
        if filter_type and message.message_type.value != filter_type:
            return False
        
        if session_filter and message.session_id != session_filter:
            return False
        
        return True
    
    def process_file(
        self, 
        file_path: Path, 
        compact: bool = False,
        filter_type: Optional[str] = None,
        session_filter: Optional[str] = None
    ):
        """
        Process a log file and display messages.
        
        Args:
            file_path: Path to log file
            compact: Use compact display format
            filter_type: Optional message type filter
            session_filter: Optional session ID filter
        """
        if not self._validate_file_path(file_path):
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    message = self.parse_message(line)
                    if message and self._should_display(message, filter_type, session_filter):
                        formatted = self.format_message(message, compact)
                        self.console.print(formatted)
                        if not compact:
                            self.console.print()
        except Exception as e:
            self.logger.error(f"Failed to process file {file_path}: {e}")
    
    def follow_file(
        self, 
        file_path: Path, 
        compact: bool = False,
        filter_type: Optional[str] = None,
        session_filter: Optional[str] = None
    ):
        """
        Follow a log file like tail -f.
        
        Args:
            file_path: Path to log file
            compact: Use compact display format
            filter_type: Optional message type filter
            session_filter: Optional session ID filter
        """
        if not self._validate_file_path(file_path):
            return
        
        try:
            # Process existing content first
            if file_path.exists():
                self.process_file(file_path, compact, filter_type, session_filter)
            
            # Set up file watcher for new content
            # Implementation would depend on specific requirements
            self.logger.info(f"Following {file_path} (Ctrl+C to stop)")
            
        except KeyboardInterrupt:
            self.logger.info("File following stopped")
        except Exception as e:
            self.logger.error(f"Failed to follow file {file_path}: {e}")
    
    def _validate_file_path(self, file_path: Path) -> bool:
        """Validate file path for security."""
        try:
            resolved_path = file_path.resolve()
            
            # Security check - ensure file exists and is readable
            if not resolved_path.exists():
                self.logger.error(f"File does not exist: {resolved_path}")
                return False
                
            if not resolved_path.is_file():
                self.logger.error(f"Path is not a file: {resolved_path}")
                return False
            
            # Check if file is readable
            with open(resolved_path, 'r') as f:
                f.read(1)  # Try to read one character
            
            return True
            
        except PermissionError:
            self.logger.error(f"Permission denied: {file_path}")
            return False
        except Exception as e:
            self.logger.error(f"Invalid file path {file_path}: {e}")
            return False