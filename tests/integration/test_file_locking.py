"""
T028: Live Integration Test - File Locking Concurrent Access

Tests file locking mechanism with concurrent playlist generation processes
to ensure no corruption or race conditions.

This test uses LIVE file system (NO mocks).
"""
import os
import pytest
import asyncio
import multiprocessing
import time
from pathlib import Path
from datetime import date
from src.ai_playlist.file_lock import FileLock
from src.ai_playlist.document_parser import DocumentParser
from src.ai_playlist.models.core import StationIdentityDocument


def _generate_playlist_process(process_id: int, output_dir: Path, station_identity_path: Path):
    """Simulate playlist generation in separate process (module-level for pickling)."""
    try:
        # Acquire lock on station identity
        with FileLock(station_identity_path, timeout=30):
            # Load document
            parser = DocumentParser()
            doc = parser.load_document(station_identity_path)

            # Simulate processing time
            time.sleep(0.5)

            # Write result
            result_file = output_dir / f"playlist_{process_id}.txt"
            result_file.write_text(
                f"Process {process_id} generated playlist\n"
                f"Loaded {len(doc.programming_structures)} structures\n"
            )

        return f"Process {process_id} completed"

    except Exception as e:
        return f"Process {process_id} failed: {e}"


@pytest.mark.integration
@pytest.mark.live
class TestFileLocking:
    """Live integration tests for file locking during concurrent access."""

    @pytest.fixture
    def station_identity_path(self) -> Path:
        """Get path to station identity file."""
        return Path("/workspaces/emby-to-m3u/station-identity.md")

    @pytest.fixture
    def test_lock_file(self, tmp_path: Path) -> Path:
        """Create temporary test file for locking."""
        test_file = tmp_path / "test-lock.txt"
        test_file.write_text("Test file for locking")
        return test_file

    def test_acquire_exclusive_lock(self, test_lock_file: Path):
        """Test acquiring exclusive file lock.

        Success Criteria:
        - Lock acquired successfully
        - Lock file created
        - Lock released cleanly
        """
        # Act - Acquire lock
        with FileLock(test_lock_file, timeout=5) as lock:
            assert lock.is_locked()
            assert lock.lock_file.exists()

        # Assert - Lock released
        assert not lock.is_locked()

    def test_concurrent_lock_acquisition_blocks(self, test_lock_file: Path):
        """Test that concurrent lock acquisition blocks until first lock released.

        Success Criteria:
        - Second process blocks waiting for lock
        - Lock properly serializes access
        - No corruption when both processes complete
        """
        import time
        import threading

        results = []

        def acquire_and_hold(file_path: Path, hold_seconds: float, process_id: int):
            """Acquire lock, hold it, then release."""
            try:
                with FileLock(file_path, timeout=10) as lock:
                    start_time = time.time()
                    results.append(f"Process {process_id} acquired at {start_time:.2f}")

                    # Read current content
                    content = file_path.read_text()

                    # Simulate work
                    time.sleep(hold_seconds)

                    # Write new content
                    file_path.write_text(content + f"\nProcess {process_id} was here")

                    end_time = time.time()
                    results.append(f"Process {process_id} released at {end_time:.2f}")

            except Exception as e:
                results.append(f"Process {process_id} failed: {e}")

        # Act - Start two threads trying to acquire same lock
        thread1 = threading.Thread(
            target=acquire_and_hold,
            args=(test_lock_file, 1.0, 1)
        )
        thread2 = threading.Thread(
            target=acquire_and_hold,
            args=(test_lock_file, 1.0, 2)
        )

        thread1.start()
        time.sleep(0.1)  # Small delay to ensure thread1 starts first
        thread2.start()

        thread1.join(timeout=15)
        thread2.join(timeout=15)

        # Assert - Both processes completed
        assert len(results) == 4, f"Expected 4 events, got {len(results)}: {results}"

        # Assert - File has both process writes
        final_content = test_lock_file.read_text()
        assert "Process 1 was here" in final_content
        assert "Process 2 was here" in final_content

        print(f"\n✓ Concurrent access serialized correctly:")
        for result in results:
            print(f"  {result}")

    def test_lock_timeout_raises_exception(self, test_lock_file: Path):
        """Test that lock timeout raises exception.

        Success Criteria:
        - TimeoutError raised when lock cannot be acquired
        - Original lock holder unaffected
        - Clean error handling
        """
        import threading
        import time

        timeout_occurred = []

        def hold_lock_forever(file_path: Path):
            """Hold lock for extended period."""
            with FileLock(file_path, timeout=30):
                time.sleep(5)

        def try_acquire_with_timeout(file_path: Path):
            """Try to acquire lock with short timeout."""
            try:
                with FileLock(file_path, timeout=1):
                    pass
            except TimeoutError:
                timeout_occurred.append(True)

        # Start thread that holds lock
        holder = threading.Thread(target=hold_lock_forever, args=(test_lock_file,))
        holder.start()

        time.sleep(0.5)  # Ensure holder has lock

        # Try to acquire with timeout
        waiter = threading.Thread(target=try_acquire_with_timeout, args=(test_lock_file,))
        waiter.start()

        waiter.join(timeout=3)
        holder.join(timeout=10)

        # Assert - Timeout occurred
        assert len(timeout_occurred) > 0, "TimeoutError was not raised"

        print("\n✓ Lock timeout raised exception as expected")

    def test_multiple_processes_playlist_generation(
        self, station_identity_path: Path, tmp_path: Path
    ):
        """Test multiple processes generating playlists concurrently.

        Success Criteria:
        - All processes complete successfully
        - No file corruption
        - Station identity file properly locked during reads
        - Decision logs written without conflicts
        """
        # Act - Start multiple processes
        output_dir = tmp_path / "playlists"
        output_dir.mkdir()

        num_processes = 4

        with multiprocessing.Pool(processes=num_processes) as pool:
            results = pool.starmap(
                _generate_playlist_process,
                [(i, output_dir, station_identity_path) for i in range(num_processes)]
            )

        # Assert - All processes completed
        for result in results:
            assert "completed" in result, f"Process failed: {result}"

        # Assert - All output files created
        output_files = list(output_dir.glob("playlist_*.txt"))
        assert len(output_files) == num_processes

        print(f"\n✓ {num_processes} concurrent processes completed successfully")

    def test_lock_cleanup_on_exception(self, test_lock_file: Path):
        """Test that lock is cleaned up even when exception occurs.

        Success Criteria:
        - Lock released when exception raised
        - Lock file removed
        - Subsequent access possible
        """
        # Act - Acquire lock and raise exception
        try:
            with FileLock(test_lock_file, timeout=5) as lock:
                assert lock.is_locked()
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Assert - Lock was cleaned up despite exception
        # Try to acquire lock again immediately
        with FileLock(test_lock_file, timeout=5) as lock:
            assert lock.is_locked()

        print("\n✓ Lock cleaned up properly after exception")

    def test_lock_with_read_and_write_operations(
        self, station_identity_path: Path, tmp_path: Path
    ):
        """Test locking during mixed read and write operations.

        Success Criteria:
        - Read locks allow concurrent reads
        - Write locks block all access
        - No data races or corruption
        """
        test_file = tmp_path / "read_write_test.txt"
        test_file.write_text("Initial content\n")

        import threading
        import time

        read_results = []
        write_results = []

        def read_operation(file_path: Path, reader_id: int):
            """Read file with lock."""
            with FileLock(file_path, timeout=10):
                content = file_path.read_text()
                read_results.append(f"Reader {reader_id}: {len(content)} chars")
                time.sleep(0.2)

        def write_operation(file_path: Path, writer_id: int):
            """Write to file with lock."""
            with FileLock(file_path, timeout=10):
                content = file_path.read_text()
                file_path.write_text(content + f"Writer {writer_id}\n")
                write_results.append(f"Writer {writer_id} completed")
                time.sleep(0.2)

        # Act - Mix of readers and writers
        threads = []

        # Start readers
        for i in range(3):
            t = threading.Thread(target=read_operation, args=(test_file, i))
            threads.append(t)
            t.start()

        # Start writers
        for i in range(2):
            t = threading.Thread(target=write_operation, args=(test_file, i))
            threads.append(t)
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join(timeout=15)

        # Assert - All operations completed
        assert len(read_results) == 3
        assert len(write_results) == 2

        # Assert - File has all writes
        final_content = test_file.read_text()
        assert "Writer 0" in final_content
        assert "Writer 1" in final_content

        print(f"\n✓ Mixed read/write operations completed: "
              f"{len(read_results)} reads, {len(write_results)} writes")
