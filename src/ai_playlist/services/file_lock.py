"""
File locking service for safe concurrent file access.

Provides cross-platform file locking with:
- fcntl-based locking on Unix/Linux
- Windows fallback using file-based semaphores
- Configurable timeout and retry logic
- Context manager support for automatic release
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class FileLockError(Exception):
    """Raised when file lock cannot be acquired."""
    pass


class FileLockService:
    """
    Cross-platform file locking service.

    Features:
    - Uses fcntl on Unix/Linux for robust file locking
    - Falls back to file-based semaphores on Windows
    - Configurable timeout and retry intervals
    - Automatic cleanup on context manager exit

    Example:
        >>> lock = FileLockService("/tmp/myfile.lock", timeout=5.0)
        >>> with lock:
        ...     # Critical section - file is locked
        ...     write_to_file()
    """

    def __init__(self, lock_file: str, timeout: float = 10.0, retry_interval: float = 0.1):
        """
        Initialize file lock service.

        Args:
            lock_file: Path to lock file (created if doesn't exist)
            timeout: Maximum seconds to wait for lock (0 = no wait)
            retry_interval: Seconds between retry attempts
        """
        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self.retry_interval = retry_interval
        self._fd: Optional[int] = None
        self._is_locked = False
        self._use_fcntl = sys.platform != 'win32'

        # Ensure lock file directory exists
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self) -> bool:
        """
        Acquire the file lock.

        Returns:
            True if lock acquired, False if timeout

        Raises:
            FileLockError: If lock cannot be acquired due to system error
        """
        if self._is_locked:
            return True

        start_time = time.time()

        while True:
            try:
                if self._use_fcntl:
                    self._acquire_fcntl()
                else:
                    self._acquire_windows()

                self._is_locked = True
                return True

            except BlockingIOError:
                # Lock is held by another process
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    return False

                time.sleep(self.retry_interval)

            except Exception as e:
                raise FileLockError(f"Failed to acquire lock: {e}") from e

    def _acquire_fcntl(self):
        """Acquire lock using fcntl (Unix/Linux)."""
        import fcntl

        # Open file descriptor if not already open
        if self._fd is None:
            self._fd = os.open(str(self.lock_file), os.O_RDWR | os.O_CREAT)

        # Try to acquire exclusive lock (non-blocking)
        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _acquire_windows(self):
        """Acquire lock using file-based semaphore (Windows)."""
        # Try to create lock file exclusively
        # This will fail if file already exists
        try:
            self._fd = os.open(
                str(self.lock_file),
                os.O_CREAT | os.O_EXCL | os.O_RDWR
            )
        except FileExistsError:
            raise BlockingIOError("Lock file already exists")

    def release(self):
        """
        Release the file lock.

        Safe to call multiple times.
        """
        if not self._is_locked:
            return

        try:
            if self._use_fcntl:
                self._release_fcntl()
            else:
                self._release_windows()
        finally:
            self._is_locked = False
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None

    def _release_fcntl(self):
        """Release fcntl lock."""
        import fcntl

        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)

    def _release_windows(self):
        """Release Windows lock by removing lock file."""
        try:
            self.lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self):
        """Context manager entry - acquire lock."""
        if not self.acquire():
            raise FileLockError(
                f"Could not acquire lock on {self.lock_file} within {self.timeout}s"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock."""
        self.release()
        return False

    def __del__(self):
        """Cleanup - ensure lock is released."""
        self.release()

    @property
    def is_locked(self) -> bool:
        """Check if lock is currently held."""
        return self._is_locked
