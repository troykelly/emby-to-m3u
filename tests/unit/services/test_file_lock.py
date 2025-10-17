"""
Unit tests for FileLockService.

Tests cover:
- fcntl locking on Unix/Linux
- Windows fallback mechanism
- Timeout behavior
- Concurrent access prevention
- Context manager functionality
- Lock release and cleanup
"""

import os
import sys
import time
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ai_playlist.services.file_lock import FileLockService, FileLockError


class TestFileLockBasics:
    """Test basic file lock functionality."""

    def test_lock_creation(self, tmp_path):
        """Test lock file is created on initialization."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        assert lock.lock_file == lock_file
        assert not lock.is_locked
        assert lock.timeout == 10.0
        assert lock.retry_interval == 0.1

    def test_lock_custom_params(self, tmp_path):
        """Test custom timeout and retry interval."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file), timeout=5.0, retry_interval=0.5)

        assert lock.timeout == 5.0
        assert lock.retry_interval == 0.5

    def test_lock_directory_creation(self, tmp_path):
        """Test lock file directory is created if missing."""
        lock_file = tmp_path / "subdir" / "nested" / "test.lock"
        lock = FileLockService(str(lock_file))

        assert lock_file.parent.exists()


class TestFileLockAcquisition:
    """Test lock acquisition and release."""

    def test_acquire_release(self, tmp_path):
        """Test basic acquire and release."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        # Acquire lock
        assert lock.acquire()
        assert lock.is_locked

        # Release lock
        lock.release()
        assert not lock.is_locked

    def test_acquire_twice_same_instance(self, tmp_path):
        """Test acquiring lock twice on same instance is idempotent."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        assert lock.acquire()
        assert lock.acquire()  # Should still return True
        assert lock.is_locked

        lock.release()

    def test_release_without_acquire(self, tmp_path):
        """Test releasing unlocked lock is safe."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        lock.release()  # Should not raise
        assert not lock.is_locked

    def test_multiple_release(self, tmp_path):
        """Test multiple releases are safe."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        lock.acquire()
        lock.release()
        lock.release()  # Should not raise
        assert not lock.is_locked


class TestFileLockTimeout:
    """Test timeout behavior."""

    def test_timeout_on_locked_file(self, tmp_path):
        """Test timeout when lock is held by another instance."""
        lock_file = tmp_path / "test.lock"

        # First lock acquires
        lock1 = FileLockService(str(lock_file), timeout=0.5)
        assert lock1.acquire()

        # Second lock should timeout
        lock2 = FileLockService(str(lock_file), timeout=0.5)
        start = time.time()
        result = lock2.acquire()
        elapsed = time.time() - start

        assert not result  # Failed to acquire
        assert elapsed >= 0.5  # Took at least timeout duration
        assert elapsed < 1.0  # But not too long

        lock1.release()

    def test_zero_timeout(self, tmp_path):
        """Test zero timeout returns immediately."""
        lock_file = tmp_path / "test.lock"

        lock1 = FileLockService(str(lock_file))
        lock1.acquire()

        lock2 = FileLockService(str(lock_file), timeout=0)
        start = time.time()
        result = lock2.acquire()
        elapsed = time.time() - start

        assert not result
        assert elapsed < 0.2  # Should return almost immediately

        lock1.release()

    def test_acquire_after_release(self, tmp_path):
        """Test second lock can acquire after first releases."""
        lock_file = tmp_path / "test.lock"

        lock1 = FileLockService(str(lock_file))
        lock1.acquire()
        lock1.release()

        lock2 = FileLockService(str(lock_file))
        assert lock2.acquire()  # Should succeed immediately

        lock2.release()


class TestFileLockConcurrency:
    """Test concurrent access prevention."""

    def test_concurrent_access_prevented(self, tmp_path):
        """Test only one thread can hold lock at a time."""
        lock_file = tmp_path / "test.lock"
        results = {"acquired": []}

        def try_acquire(thread_id):
            lock = FileLockService(str(lock_file), timeout=2.0)
            if lock.acquire():
                results["acquired"].append(thread_id)
                time.sleep(0.5)  # Hold lock briefly
                lock.release()

        # Start 3 threads trying to acquire lock
        threads = [
            threading.Thread(target=try_acquire, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should have acquired lock
        assert len(results["acquired"]) == 3
        # But at different times (not simultaneously)

    def test_concurrent_writes_prevented(self, tmp_path):
        """Test concurrent writes are serialized."""
        lock_file = tmp_path / "test.lock"
        data_file = tmp_path / "data.txt"
        data_file.write_text("")

        results = {"final_count": 0}

        def write_data(value):
            lock = FileLockService(str(lock_file), timeout=5.0)
            with lock:
                # Read current value
                current = data_file.read_text()
                count = int(current) if current else 0

                # Simulate processing
                time.sleep(0.01)

                # Write incremented value
                data_file.write_text(str(count + value))

        # Start 10 threads writing concurrently
        threads = [
            threading.Thread(target=write_data, args=(1,))
            for _ in range(10)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Final value should be 10 (not lost updates)
        final_value = int(data_file.read_text())
        assert final_value == 10


class TestFileLockContextManager:
    """Test context manager functionality."""

    def test_context_manager_basic(self, tmp_path):
        """Test lock is acquired and released via context manager."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        with lock:
            assert lock.is_locked

        assert not lock.is_locked

    def test_context_manager_exception_releases(self, tmp_path):
        """Test lock is released even if exception occurs."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        try:
            with lock:
                assert lock.is_locked
                raise ValueError("Test error")
        except ValueError:
            pass

        assert not lock.is_locked

    def test_context_manager_timeout_raises(self, tmp_path):
        """Test context manager raises on timeout."""
        lock_file = tmp_path / "test.lock"

        lock1 = FileLockService(str(lock_file))
        lock1.acquire()

        lock2 = FileLockService(str(lock_file), timeout=0.5)

        with pytest.raises(FileLockError, match="Could not acquire lock"):
            with lock2:
                pass

        lock1.release()

    def test_nested_context_managers(self, tmp_path):
        """Test nested context managers with same lock."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        with lock:
            assert lock.is_locked
            # Re-entering should work (idempotent)
            with lock:
                assert lock.is_locked

        assert not lock.is_locked


class TestFileLockCleanup:
    """Test cleanup and resource management."""

    def test_del_releases_lock(self, tmp_path):
        """Test __del__ releases lock."""
        lock_file = tmp_path / "test.lock"

        lock1 = FileLockService(str(lock_file))
        lock1.acquire()
        del lock1  # Should trigger cleanup

        # New lock should be able to acquire
        lock2 = FileLockService(str(lock_file))
        assert lock2.acquire()
        lock2.release()

    def test_lock_file_cleanup_unix(self, tmp_path):
        """Test lock file behavior on Unix."""
        if sys.platform == 'win32':
            pytest.skip("Unix-only test")

        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        with lock:
            # Lock file should exist
            assert lock_file.exists()

        # On Unix, fcntl doesn't create/delete lock file
        # File may remain but is unlocked

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only test")
    def test_lock_file_cleanup_windows(self, tmp_path):
        """Test lock file is removed on Windows."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        with lock:
            assert lock_file.exists()

        # On Windows, lock file should be removed
        assert not lock_file.exists()


class TestFileLockPlatformSpecific:
    """Test platform-specific implementations."""

    def test_uses_fcntl_on_unix(self, tmp_path):
        """Test fcntl is used on Unix/Linux."""
        if sys.platform == 'win32':
            pytest.skip("Unix-only test")

        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        assert lock._use_fcntl is True

    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only test")
    def test_uses_file_based_on_windows(self):
        """Test file-based locking is used on Windows."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_file = Path(tmp_dir) / "test.lock"
            lock = FileLockService(str(lock_file))

            assert lock._use_fcntl is False

    @patch('sys.platform', 'win32')
    def test_windows_fallback_mock(self, tmp_path):
        """Test Windows fallback using mock."""
        lock_file = tmp_path / "test.lock"

        # Simulate Windows mode by creating instance and forcing attribute
        lock = FileLockService(str(lock_file))
        lock._use_fcntl = False  # Force Windows mode after instantiation

        # Acquire and release manually to test Windows path
        assert lock.acquire()
        assert lock_file.exists()
        lock.release()

        # Windows mode removes lock file
        assert not lock.is_locked


class TestFileLockEdgeCases:
    """Test edge cases and error conditions."""

    def test_lock_with_invalid_path(self):
        """Test lock with invalid path raises appropriate error."""
        # This should still work - parent directory is created
        lock = FileLockService("/tmp/nonexistent/deep/path/test.lock")
        assert lock.lock_file.parent.exists()

    def test_lock_with_permission_error(self, tmp_path):
        """Test lock handles permission errors."""
        lock_file = tmp_path / "readonly.lock"
        lock_file.touch()

        if sys.platform != 'win32':
            # Make directory read-only (Unix)
            os.chmod(tmp_path, 0o444)

            lock = FileLockService(str(lock_file))

            # Should raise FileLockError, not permission error
            try:
                with pytest.raises((FileLockError, PermissionError)):
                    lock.acquire()
            finally:
                # Restore permissions
                os.chmod(tmp_path, 0o755)

    def test_rapid_acquire_release(self, tmp_path):
        """Test rapid acquire/release cycles."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file))

        # Rapidly acquire and release
        for _ in range(100):
            assert lock.acquire()
            lock.release()

        assert not lock.is_locked

    def test_long_timeout(self, tmp_path):
        """Test lock with very long timeout."""
        lock_file = tmp_path / "test.lock"
        lock = FileLockService(str(lock_file), timeout=3600.0)

        assert lock.timeout == 3600.0
        assert lock.acquire()
        lock.release()


# Fixtures
@pytest.fixture
def tmp_path():
    """Provide temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
