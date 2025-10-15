"""
File locking utility for concurrent access control.

Provides cross-platform file locking with POSIX fcntl (preferred) and Windows msvcrt fallback.
Implements exclusive locks to prevent race conditions when multiple processes access
station-identity.md or other shared resources.

FR-031: Concurrent access control for station identity documents.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Platform-specific imports - Initialize all variables at module level
HAS_MSVCRT = False
HAS_PORTALOCKER = False
HAS_FCNTL = False
msvcrt = None  # type: ignore
portalocker = None  # type: ignore

if sys.platform == "win32":
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False
        try:
            import portalocker  # type: ignore
            HAS_PORTALOCKER = True
        except ImportError:
            HAS_PORTALOCKER = False
else:
    import fcntl
    HAS_FCNTL = True


class FileLockError(Exception):
    """Base exception for file locking errors."""
    pass


class FileLockTimeout(FileLockError):
    """Raised when lock acquisition times out."""
    pass


class FileLock:
    """
    Context manager for exclusive file locking.

    Supports POSIX systems (Linux, macOS) via fcntl and Windows via msvcrt/portalocker.

    Examples:
        # Read operation with 30s timeout
        with FileLock("/path/to/file.md", timeout=30):
            content = Path("/path/to/file.md").read_text()

        # Write operation with 60s timeout
        with FileLock("/path/to/file.md", timeout=60, mode="write"):
            Path("/path/to/file.md").write_text(content)

    Attributes:
        path: Path to the file to lock
        timeout: Maximum seconds to wait for lock acquisition
        mode: Lock mode ("read" or "write") - affects timeout defaults
    """

    DEFAULT_READ_TIMEOUT = 30
    DEFAULT_WRITE_TIMEOUT = 60

    def __init__(
        self,
        path: str | Path,
        timeout: Optional[int] = None,
        mode: str = "read"
    ):
        """
        Initialize file lock.

        Args:
            path: Path to the file to lock
            timeout: Timeout in seconds (defaults: 30s read, 60s write)
            mode: Lock mode - "read" or "write"

        Raises:
            FileLockError: If platform lacks locking support
        """
        self.path = Path(path).resolve()
        self.mode = mode

        # Set timeout based on mode if not specified
        if timeout is None:
            timeout = (
                self.DEFAULT_WRITE_TIMEOUT if mode == "write"
                else self.DEFAULT_READ_TIMEOUT
            )
        self.timeout = timeout

        self._lock_file: Optional[object] = None
        self._lock_path = self.path.parent / f".{self.path.name}.lock"
        self._locked = False

        # Validate platform support
        if sys.platform == "win32" and not (HAS_MSVCRT or HAS_PORTALOCKER):
            raise FileLockError(
                "Windows platform requires msvcrt or portalocker for file locking. "
                "Install portalocker: pip install portalocker"
            )

    def __enter__(self):
        """Acquire exclusive lock on file."""
        self._acquire_lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock on file."""
        self._release_lock()

    def is_locked(self) -> bool:
        """
        Check if the lock is currently held.

        Returns:
            True if lock is currently held, False otherwise
        """
        return self._locked

    @property
    def lock_file(self) -> Path:
        """
        Get the path to the lock file.

        Returns:
            Path to the lock file
        """
        return self._lock_path

    def _acquire_lock(self) -> None:
        """
        Acquire exclusive lock with timeout.

        Raises:
            FileLockTimeout: If lock cannot be acquired within timeout
            FileLockError: If locking mechanism fails
        """
        start_time = time.time()

        # Ensure lock directory exists
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                if sys.platform == "win32":
                    self._acquire_lock_windows()
                else:
                    self._acquire_lock_posix()

                self._locked = True
                logger.debug(
                    f"Acquired {self.mode} lock on {self.path} "
                    f"(timeout={self.timeout}s)"
                )
                return

            except (IOError, OSError) as e:
                elapsed = time.time() - start_time
                if elapsed >= self.timeout:
                    # Raise standard TimeoutError for compatibility
                    raise TimeoutError(
                        f"Failed to acquire lock on {self.path} after {self.timeout}s"
                    ) from e

                # Wait briefly before retry
                time.sleep(0.1)

    def _acquire_lock_posix(self) -> None:
        """Acquire lock using POSIX fcntl (Linux, macOS)."""
        # Open lock file (create if needed)
        self._lock_file = open(str(self._lock_path), "w", encoding="utf-8")

        # Attempt exclusive lock (non-blocking)
        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _acquire_lock_windows(self) -> None:
        """Acquire lock using Windows msvcrt or portalocker."""
        # Open lock file (create if needed)
        self._lock_file = open(str(self._lock_path), "w", encoding="utf-8")

        if HAS_MSVCRT:
            # Use msvcrt for locking
            try:
                msvcrt.locking(
                    self._lock_file.fileno(),
                    msvcrt.LK_NBLCK,  # Non-blocking exclusive lock
                    1
                )
            except IOError as e:
                self._lock_file.close()
                self._lock_file = None
                raise e

        elif HAS_PORTALOCKER:
            # Use portalocker for locking
            try:
                portalocker.lock(
                    self._lock_file,
                    portalocker.LOCK_EX | portalocker.LOCK_NB
                )
            except portalocker.LockException as e:
                self._lock_file.close()
                self._lock_file = None
                raise IOError("Lock already held") from e

    def _release_lock(self) -> None:
        """Release lock and clean up lock file."""
        if self._lock_file is None:
            return

        try:
            if sys.platform != "win32":
                # POSIX: unlock via fcntl
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            elif HAS_MSVCRT:
                # Windows msvcrt: unlock
                msvcrt.locking(
                    self._lock_file.fileno(),
                    msvcrt.LK_UNLCK,
                    1
                )
            elif HAS_PORTALOCKER:
                # Windows portalocker: unlock
                portalocker.unlock(self._lock_file)

            self._lock_file.close()

            # Clean up lock file
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError:
                pass  # Lock file cleanup is best-effort

            logger.debug(f"Released lock on {self.path}")

        finally:
            self._lock_file = None
            self._locked = False


def test_concurrent_locks():
    """
    Test that concurrent processes cannot acquire the same lock.

    This function is used for testing the file locking mechanism.
    """
    import tempfile
    from multiprocessing import Process

    def worker(path: str, worker_id: int, results: list):
        """Worker process that attempts to acquire lock."""
        try:
            with FileLock(path, timeout=1):
                # Simulate work
                time.sleep(2)
                results.append(f"Worker {worker_id} succeeded")
        except FileLockTimeout:
            results.append(f"Worker {worker_id} timed out")

    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Start two concurrent processes
        results = []
        p1 = Process(target=worker, args=(tmp_path, 1, results))
        p2 = Process(target=worker, args=(tmp_path, 2, results))

        p1.start()
        time.sleep(0.1)  # Ensure p1 acquires lock first
        p2.start()

        p1.join()
        p2.join()

        # Verify only one succeeded
        succeeded = [r for r in results if "succeeded" in r]
        timed_out = [r for r in results if "timed out" in r]

        assert len(succeeded) == 1, "Only one worker should succeed"
        assert len(timed_out) == 1, "One worker should timeout"

        print("✓ Concurrent lock test passed")

    finally:
        # Clean up
        os.unlink(tmp_path)


if __name__ == "__main__":
    # Run basic test
    test_concurrent_locks()
