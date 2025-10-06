"""Process management with intelligent timeout based on activity monitoring."""

import asyncio
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .exceptions import ProcessError, ProcessTimeoutError
from .logging_setup import get_logger
from ..config.models import TimeoutConfig


class ProcessStatus(Enum):
    """Process status enumeration."""
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    TERMINATED = "terminated"


@dataclass
class ProcessResult:
    """Result of process execution."""
    
    status: ProcessStatus
    exit_code: Optional[int]
    stdout: Optional[str]
    stderr: Optional[str]
    runtime_seconds: float
    termination_reason: Optional[str] = None


class LogActivityHandler(FileSystemEventHandler):
    """File system event handler for monitoring log activity."""
    
    def __init__(self, callback: Callable):
        """
        Initialize activity handler.
        
        Args:
            callback: Function to call when activity is detected
        """
        self.callback = callback
        self.logger = get_logger(__name__)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            self.logger.debug(f"Log activity detected: {event.src_path}")
            self.callback()


class ProcessManager:
    """Manages subprocess execution with intelligent timeout and activity monitoring."""
    
    def __init__(self, timeout_config: TimeoutConfig):
        """
        Initialize process manager.
        
        Args:
            timeout_config: Timeout configuration
        """
        self.timeout_config = timeout_config
        self.logger = get_logger(__name__)
        self.console = Console()
        
        # Process tracking
        self._processes: Dict[str, subprocess.Popen] = {}
        self._observers: Dict[str, Observer] = {}
        self._last_activity: Dict[str, float] = {}
        
        # Setup signal handlers for cleanup
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        self.logger.info(f"Received signal {signum}, cleaning up processes...")
        self.cleanup_all()
    
    def _update_activity(self, process_id: str):
        """Update last activity time for a process."""
        self._last_activity[process_id] = time.time()
        self.logger.debug(f"Activity updated for process {process_id}")
    
    def _validate_command(self, command: List[str]) -> List[str]:
        """Validate and sanitize command for security."""
        if not command or not isinstance(command, list):
            raise ValueError("Command must be a non-empty list")
        
        validated_command = []
        for i, arg in enumerate(command):
            if not isinstance(arg, str):
                raise ValueError(f"Command argument {i} must be a string: {type(arg)}")
            
            # Basic sanitization - no shell metacharacters
            if re.search(r'[;&|`$(){}[\]<>]', arg):
                raise ValueError(f"Command argument {i} contains unsafe characters: {arg}")
            
            # Limit argument length
            if len(arg) > 1000:
                raise ValueError(f"Command argument {i} too long: {len(arg)} characters")
            
            validated_command.append(arg)
        
        # Validate command name (first argument)
        cmd_name = validated_command[0]
        if '/' in cmd_name or '\\' in cmd_name:
            raise ValueError(f"Command name contains path separators: {cmd_name}")
        
        return validated_command
    
    def _validate_process_id(self, process_id: str) -> str:
        """Validate process ID for security."""
        if not isinstance(process_id, str):
            raise ValueError("Process ID must be a string")
        
        # Sanitize and validate format
        clean_id = re.sub(r'[^a-zA-Z0-9_-]', '', process_id)
        if not clean_id or clean_id != process_id:
            raise ValueError(f"Invalid process ID format: {process_id}")
        
        if len(clean_id) > 64:
            raise ValueError(f"Process ID too long: {len(clean_id)} characters")
        
        return clean_id
    
    def _validate_log_file(self, log_file: Optional[Path]) -> Optional[Path]:
        """Validate log file path for security."""
        if log_file is None:
            return None
        
        if not isinstance(log_file, Path):
            if isinstance(log_file, str):
                log_file = Path(log_file)
            else:
                raise ValueError("Log file must be a Path object or string")
        
        try:
            resolved_path = log_file.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid log file path: {e}")
        
        # Security check - ensure path is within safe directories
        safe_dirs = [
            Path.home() / ".local" / "share" / "github-automation",
            Path("/tmp") / "github-automation",
            Path.cwd() / "logs"
        ]
        
        if not any(str(resolved_path).startswith(str(safe_dir)) for safe_dir in safe_dirs):
            # Force to safe location
            safe_dir = Path.home() / ".local" / "share" / "github-automation" / "logs"
            safe_dir.mkdir(parents=True, exist_ok=True)
            resolved_path = safe_dir / f"process-{int(time.time())}.log"
        
        return resolved_path
    
    def _validate_working_dir(self, working_dir: Optional[Path]) -> Optional[Path]:
        """Validate working directory for security."""
        if working_dir is None:
            return None
        
        if not isinstance(working_dir, Path):
            if isinstance(working_dir, str):
                # Sanitize path
                clean_path = re.sub(r'\.\./', '', working_dir)
                working_dir = Path(clean_path)
            else:
                raise ValueError("Working directory must be a Path object or string")
        
        try:
            resolved_path = working_dir.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid working directory: {e}")
        
        # Security checks
        if not resolved_path.exists():
            raise ValueError(f"Working directory does not exist: {resolved_path}")
        if not resolved_path.is_dir():
            raise ValueError(f"Working directory is not a directory: {resolved_path}")
        
        return resolved_path
    
    def _validate_environment(self, env: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Validate and sanitize environment variables."""
        if env is None:
            return None
        
        if not isinstance(env, dict):
            raise ValueError("Environment must be a dictionary")
        
        validated_env = {}
        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"Environment key/value must be strings: {key}={value}")
            
            # Validate key format
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
                raise ValueError(f"Invalid environment variable name: {key}")
            
            # Limit lengths
            if len(key) > 100:
                raise ValueError(f"Environment variable name too long: {key}")
            if len(value) > 10000:
                raise ValueError(f"Environment variable value too long for {key}")
            
            validated_env[key] = value
        
        return validated_env
    
    def _sanitize_command_for_logging(self, command: List[str]) -> List[str]:
        """Sanitize command for safe logging."""
        safe_command = []
        for arg in command:
            # Basic pattern to detect potential credentials
            if re.search(r'(token|password|secret|key|auth)=', arg.lower()):
                # Replace value part after = with [REDACTED]
                if '=' in arg:
                    key, _ = arg.split('=', 1)
                    safe_command.append(f"{key}=[REDACTED]")
                else:
                    safe_command.append(arg)
            else:
                safe_command.append(arg)
        return safe_command
    
    def _check_log_file_activity(self, log_file: Path, process_id: str) -> bool:
        """
        Check if log file has recent activity.
        
        Args:
            log_file: Path to log file
            process_id: Process identifier
            
        Returns:
            True if there's recent activity
        """
        if not log_file.exists():
            return False
        
        try:
            # Get file modification time
            mtime = log_file.stat().st_mtime
            last_known = self._last_activity.get(process_id, 0)
            
            if mtime > last_known:
                self._update_activity(process_id)
                return True
                
            return False
            
        except Exception as e:
            self.logger.warning(f"Failed to check log file activity: {e}")
            return False
    
    def _setup_file_watcher(self, log_file: Path, process_id: str) -> Observer:
        """
        Set up file system watcher for log file.
        
        Args:
            log_file: Path to log file to watch
            process_id: Process identifier
            
        Returns:
            Observer instance
        """
        observer = Observer()
        
        # Create callback for activity updates
        def activity_callback():
            self._update_activity(process_id)
        
        handler = LogActivityHandler(activity_callback)
        
        # Watch the directory containing the log file
        watch_dir = log_file.parent
        observer.schedule(handler, str(watch_dir), recursive=False)
        
        observer.start()
        self.logger.debug(f"Started file watcher for {log_file}")
        
        return observer
    
    async def run_with_timeout(
        self,
        command: List[str],
        process_id: str,
        log_file: Optional[Path] = None,
        working_dir: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> ProcessResult:
        """
        Run command with intelligent timeout based on activity monitoring.
        
        Args:
            command: Command and arguments to execute
            process_id: Unique identifier for this process
            log_file: Optional log file to monitor for activity
            working_dir: Working directory for process
            env: Environment variables
            progress_callback: Optional callback for progress updates
            
        Returns:
            ProcessResult with execution details
            
        Raises:
            ValueError: If parameters are invalid or insecure
            ProcessError: If process execution fails
        """
        start_time = time.time()
        
        # Validate and sanitize all inputs
        validated_command = self._validate_command(command)
        validated_process_id = self._validate_process_id(process_id)
        validated_log_file = self._validate_log_file(log_file)
        validated_working_dir = self._validate_working_dir(working_dir)
        validated_env = self._validate_environment(env)
        
        # Log command safely (without exposing credentials)
        safe_command = self._sanitize_command_for_logging(validated_command)
        self.logger.info(f"Starting process {validated_process_id}: {' '.join(safe_command)}")
        
        log_file_handle = None
        try:
            # Prepare process arguments with secure file handling
            if validated_log_file:
                # Ensure log file directory exists with proper permissions
                validated_log_file.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                log_file_handle = open(validated_log_file, 'w', encoding='utf-8')
                stdout_target = log_file_handle
            else:
                stdout_target = subprocess.PIPE
            
            kwargs = {
                'stdout': stdout_target,
                'stderr': subprocess.STDOUT,
                'text': True,
                'cwd': validated_working_dir,
                'env': validated_env,
                'shell': False,  # Explicitly disable shell for security
                'start_new_session': True,  # Isolate process group
            }
            
            # Start process with validated parameters
            process = subprocess.Popen(validated_command, **kwargs)
            self._processes[validated_process_id] = process
            self._update_activity(validated_process_id)
            
            # Setup file watcher if log file is provided
            observer = None
            if validated_log_file:
                observer = self._setup_file_watcher(validated_log_file, validated_process_id)
                self._observers[validated_process_id] = observer
            
            # Monitor process with intelligent timeout
            return await self._monitor_process(
                process, validated_process_id, validated_log_file, start_time, progress_callback
            )
            
        except Exception as e:
            runtime = time.time() - start_time
            self.logger.error(f"Failed to start process {validated_process_id}: {e}")
            return ProcessResult(
                status=ProcessStatus.FAILED,
                exit_code=None,
                stdout=None,
                stderr=str(e),
                runtime_seconds=runtime,
                termination_reason=f"Failed to start: {e}"
            )
        finally:
            # Ensure file handle is properly closed
            if log_file_handle:
                try:
                    log_file_handle.close()
                except Exception as e:
                    self.logger.warning(f"Failed to close log file handle: {e}")
            
            # Cleanup process resources
            self._cleanup_process(validated_process_id)
    
    async def _monitor_process(
        self,
        process: subprocess.Popen,
        process_id: str,
        log_file: Optional[Path],
        start_time: float,
        progress_callback: Optional[Callable[[str], None]]
    ) -> ProcessResult:
        """
        Monitor process execution with intelligent timeout.
        
        Args:
            process: Process to monitor
            process_id: Process identifier
            log_file: Optional log file to monitor
            start_time: Process start time
            progress_callback: Optional progress callback
            
        Returns:
            ProcessResult with execution details
        """
        timeout_seconds = self.timeout_config.inactivity_minutes * 60
        check_interval = self.timeout_config.check_interval_seconds
        
        stdout_data = []
        stderr_data = []
        
        while True:
            # Check if process is still running
            poll_result = process.poll()
            if poll_result is not None:
                # Process completed
                runtime = time.time() - start_time
                
                # Collect any remaining output
                if process.stdout:
                    remaining_stdout = process.stdout.read()
                    if remaining_stdout:
                        stdout_data.append(remaining_stdout)
                
                status = ProcessStatus.COMPLETED if poll_result == 0 else ProcessStatus.FAILED
                
                self.logger.info(
                    f"Process {process_id} completed with exit code {poll_result} "
                    f"after {runtime:.1f} seconds"
                )
                
                return ProcessResult(
                    status=status,
                    exit_code=poll_result,
                    stdout=''.join(stdout_data) if stdout_data else None,
                    stderr=''.join(stderr_data) if stderr_data else None,
                    runtime_seconds=runtime
                )
            
            # Check for activity timeout
            current_time = time.time()
            last_activity = self._last_activity.get(process_id, start_time)
            inactive_time = current_time - last_activity
            
            if log_file:
                # Check log file for new activity
                self._check_log_file_activity(log_file, process_id)
                last_activity = self._last_activity.get(process_id, start_time)
                inactive_time = current_time - last_activity
            
            # Check for inactivity timeout
            if inactive_time > timeout_seconds:
                runtime = time.time() - start_time
                self.logger.warning(
                    f"Process {process_id} inactive for {inactive_time:.1f} seconds, terminating..."
                )
                
                # Terminate process
                try:
                    process.terminate()
                    # Give it a moment to terminate gracefully
                    await asyncio.sleep(2)
                    if process.poll() is None:
                        process.kill()
                except Exception as e:
                    self.logger.error(f"Failed to terminate process {process_id}: {e}")
                
                return ProcessResult(
                    status=ProcessStatus.TIMEOUT,
                    exit_code=process.poll(),
                    stdout=''.join(stdout_data) if stdout_data else None,
                    stderr=''.join(stderr_data) if stderr_data else None,
                    runtime_seconds=runtime,
                    termination_reason=f"Inactive for {inactive_time:.1f} seconds"
                )
            
            # Progress callback
            if progress_callback:
                remaining_time = timeout_seconds - inactive_time
                progress_callback(
                    f"Running... {remaining_time/60:.1f} minutes until timeout"
                )
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    def _cleanup_process(self, process_id: str):
        """Clean up process resources."""
        # Stop file observer
        if process_id in self._observers:
            try:
                self._observers[process_id].stop()
                self._observers[process_id].join(timeout=1)
            except Exception as e:
                self.logger.warning(f"Failed to stop observer for {process_id}: {e}")
            del self._observers[process_id]
        
        # Remove from tracking
        if process_id in self._processes:
            del self._processes[process_id]
        
        if process_id in self._last_activity:
            del self._last_activity[process_id]
        
        self.logger.debug(f"Cleaned up process {process_id}")
    
    def cleanup_all(self):
        """Clean up all processes and resources."""
        self.logger.info("Cleaning up all processes...")
        
        # Terminate all running processes
        for process_id, process in list(self._processes.items()):
            try:
                if process.poll() is None:
                    self.logger.info(f"Terminating process {process_id}")
                    process.terminate()
                    
                    # Give processes time to terminate gracefully
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.logger.warning(f"Force killing process {process_id}")
                        process.kill()
                        
            except Exception as e:
                self.logger.error(f"Failed to terminate process {process_id}: {e}")
        
        # Stop all observers
        for process_id in list(self._observers.keys()):
            self._cleanup_process(process_id)
        
        self.logger.info("Process cleanup completed")
    
    def is_running(self, process_id: str) -> bool:
        """
        Check if a process is currently running.
        
        Args:
            process_id: Process identifier
            
        Returns:
            True if process is running
        """
        if process_id not in self._processes:
            return False
        
        process = self._processes[process_id]
        return process.poll() is None
    
    def get_process_status(self, process_id: str) -> Optional[ProcessStatus]:
        """
        Get current status of a process.
        
        Args:
            process_id: Process identifier
            
        Returns:
            ProcessStatus or None if process not found
        """
        if process_id not in self._processes:
            return None
        
        process = self._processes[process_id]
        if process.poll() is None:
            return ProcessStatus.RUNNING
        elif process.poll() == 0:
            return ProcessStatus.COMPLETED
        else:
            return ProcessStatus.FAILED
    
    def run_claude_flow(
        self, 
        objective: str,
        namespace: str = "default",
        agents: int = 5,
        auto_spawn: bool = False,
        non_interactive: bool = True,
        timeout: int = 3600
    ) -> ProcessResult:
        """
        Run claude-flow with specified parameters.
        
        Args:
            objective: The task objective for claude-flow
            namespace: Namespace for the hive-mind
            agents: Number of agents to spawn
            auto_spawn: Auto-spawn agents
            non_interactive: Run in non-interactive mode
            timeout: Command timeout in seconds
            
        Returns:
            ProcessResult with command output
        """
        # Build claude-flow command - use npx in devcontainer
        # Note: objective is a positional argument, not a flag!
        command = [
            "npx",
            "--yes",
            "claude-flow@alpha",
            "hive-mind",
            "spawn",
            objective,  # Positional argument
            "--namespace", namespace,
            "--agents", str(agents)
        ]
        
        if auto_spawn:
            command.append("--auto-spawn")
        
        if non_interactive:
            command.append("--non-interactive")
        
        # Create temp file for output
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.log', delete=False) as log_file:
            log_path = Path(log_file.name)
        
        try:
            # Log command (truncate objective for readability)
            log_cmd = command.copy()
            # Find the objective (it's right after "spawn")
            if "spawn" in log_cmd:
                spawn_idx = log_cmd.index("spawn")
                if spawn_idx + 1 < len(log_cmd):
                    obj = log_cmd[spawn_idx + 1]
                    truncated = obj[:50] + "..." if len(obj) > 50 else obj
                    log_cmd[spawn_idx + 1] = truncated.replace('\n', ' ')
            self.logger.info("Running claude-flow: %s", " ".join(log_cmd))
            
            # For hive-mind spawn, we need to run it and detach after it starts
            # Run the command and capture initial output
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "CLAUDE_FLOW_NON_INTERACTIVE": "true"}
            )
            
            # For hive-mind spawn, wait for success message then kill it
            stdout_lines = []
            stderr_lines = []
            start_time = time.time()
            success = False
            
            try:
                # Read output until we see success or timeout
                # Use non-blocking I/O to avoid readline() blocking
                import select
                import fcntl
                
                # Make stdout and stderr non-blocking
                for stream in [process.stdout, process.stderr]:
                    fd = stream.fileno()
                    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                
                partial_stdout = ""
                partial_stderr = ""
                
                while time.time() - start_time < 30:  # 30 second startup timeout
                    ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
                    
                    for stream in ready:
                        try:
                            # Read available data (may be partial line)
                            chunk = stream.read(1024)
                            if not chunk:
                                continue
                                
                            if stream == process.stdout:
                                partial_stdout += chunk
                                # Process complete lines
                                while '\n' in partial_stdout:
                                    line, partial_stdout = partial_stdout.split('\n', 1)
                                    stdout_lines.append(line + '\n')
                                    self.logger.debug("STDOUT: %s", line)
                                    if "swarm spawned successfully" in line.lower() or "swarm is ready" in line.lower():
                                        success = True
                                        self.logger.info("✅ Hive-mind spawned successfully, detaching...")
                                        break
                            else:
                                partial_stderr += chunk
                                # Process complete lines
                                while '\n' in partial_stderr:
                                    line, partial_stderr = partial_stderr.split('\n', 1)
                                    stderr_lines.append(line + '\n')
                                    self.logger.debug("STDERR: %s", line)
                        except IOError:
                            # No data available yet
                            pass
                    
                    if success:
                        # Kill the process now that swarm is spawned
                        self.logger.info("Terminating spawn process...")
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        break
                    
                    # Check if process ended
                    if process.poll() is not None:
                        break
                
                stdout = ''.join(stdout_lines)
                stderr = ''.join(stderr_lines)
                stdout_lines = stdout.splitlines() if stdout else []
                stderr_lines = stderr.splitlines() if stderr else []
                
                # Log any errors
                if stderr_lines:
                    for line in stderr_lines[:10]:  # First 10 error lines
                        self.logger.debug("claude-flow stderr: %s", line)
                
                # Check result - if we detached after success, that's OK
                if success or process.returncode == 0:
                    self.logger.info("✅ Hive-mind spawned successfully")
                    return ProcessResult(
                        status=ProcessStatus.COMPLETED,
                        exit_code=0,  # Success even if we terminated it
                        stdout=stdout,
                        stderr=stderr,
                        runtime_seconds=0.0
                    )
                else:
                    self.logger.error("❌ Hive-mind failed with exit code %s", process.returncode)
                    if stderr:
                        self.logger.error("Error output: %s", stderr[:500])
                    return ProcessResult(
                        status=ProcessStatus.FAILED,
                        exit_code=process.returncode,
                        stdout=stdout,
                        stderr=stderr,
                        runtime_seconds=0.0
                    )
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise ProcessTimeoutError(
                    f"Claude-flow timed out after {timeout} seconds",
                    timeout_seconds=timeout,
                    operation="claude-flow"
                )
                
        except Exception as e:
            self.logger.error("Failed to run claude-flow: %s", e)
            raise ProcessError(f"Failed to run claude-flow: {e}")
        finally:
            # Clean up temp file
            if log_path.exists():
                log_path.unlink()
    def run_claude_swarm(self, task: str, timeout: int = 120) -> ProcessResult:
        """Run claude-flow swarm for quick single tasks with clean JSON output."""
        command = ["npx", "--yes", "claude-flow@alpha", "swarm", task, "--non-interactive", "--output-format", "text"]
        self.logger.info("Running swarm: %s", task[:50] + "..." if len(task) > 50 else task)
        self.logger.info("Full command: %s", " ".join(command[:4] + [f'"{task[:100]}..."']))
        
        try:
            start_time = time.time()
            
            # Use Popen to stream output in real-time
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                env={**os.environ, "CLAUDE_FLOW_NON_INTERACTIVE": "true"}
            )
            
            self.logger.info("🚀 Swarm process started (PID: %d), streaming output:", process.pid)
            self.logger.info("=" * 80)
            
            output_lines = []
            line_count = 0
            last_activity_time = time.time()
            inactivity_timeout = 300  # 5 minutes without output
            
            # Stream output in real-time
            while True:
                # Non-blocking read with timeout
                import select
                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                
                if ready:
                    line = process.stdout.readline()
                    if not line:
                        # Process has ended
                        break
                    
                    line = line.rstrip()
                    if line:
                        line_count += 1
                        output_lines.append(line)
                        last_activity_time = time.time()  # Reset activity timer
                        
                        # Log every line with a prefix
                        elapsed = int(time.time() - start_time)
                        self.logger.info("[SWARM %02ds L%03d] %s", elapsed, line_count, line)
                        
                        # Check for important indicators
                        line_lower = line.lower()
                        if any(word in line_lower for word in ['error', 'failed', 'exception']):
                            self.logger.error("🚨 ERROR DETECTED: %s", line)
                        elif any(word in line_lower for word in ['success', 'completed', 'done']):
                            self.logger.info("✅ SUCCESS INDICATOR: %s", line)
                        elif any(word in line_lower for word in ['starting', 'spawning', 'creating']):
                            self.logger.info("🔄 PROGRESS: %s", line)
                else:
                    # No output received, check for timeout conditions
                    
                    # Check if process has ended
                    if process.poll() is not None:
                        break
                    
                    # Check for inactivity timeout (no output for too long)
                    inactive_time = time.time() - last_activity_time
                    if inactive_time > inactivity_timeout:
                        self.logger.warning("⏱️ No output for %d seconds, terminating...", int(inactive_time))
                        process.terminate()
                        break
                    
                    # Check for absolute max timeout (but much longer)
                    total_time = time.time() - start_time
                    if total_time > timeout and total_time > 7200:  # At least 2 hours
                        self.logger.warning("⏱️ Absolute timeout reached (%d seconds), terminating...", int(total_time))
                        process.terminate()
                        break
            
            # Wait for process to complete
            return_code = process.wait(timeout=5)
            runtime = time.time() - start_time
            
            self.logger.info("=" * 80)
            self.logger.info("🏁 Swarm process completed:")
            self.logger.info("   Exit code: %d", return_code)
            self.logger.info("   Runtime: %.1f seconds", runtime)
            self.logger.info("   Output lines: %d", line_count)
            
            stdout_text = "\n".join(output_lines)
            
            if return_code == 0:
                self.logger.info("✅ Swarm completed successfully")
                # Look for actual results in the output
                if line_count < 5:
                    self.logger.warning("⚠️ Very little output - may indicate swarm didn't actually run")
                elif "no output" in stdout_text.lower() or "failed to" in stdout_text.lower():
                    self.logger.warning("⚠️ Output suggests swarm may have failed")
            else:
                self.logger.error("❌ Swarm failed with exit code %d", return_code)
            
            return ProcessResult(
                status=ProcessStatus.COMPLETED if return_code == 0 else ProcessStatus.FAILED,
                exit_code=return_code,
                stdout=stdout_text,
                stderr="",  # Combined with stdout
                runtime_seconds=runtime
            )
            
        except subprocess.TimeoutExpired:
            self.logger.error("❌ Swarm timed out after %ds", timeout)
            return ProcessResult(
                status=ProcessStatus.TIMEOUT,
                exit_code=-1,
                stdout="",
                stderr="Command timed out",
                runtime_seconds=timeout
            )
        except Exception as e:
            self.logger.error("❌ Failed to run swarm: %s", e)
            raise ProcessError(f"Failed to run swarm: {e}")

