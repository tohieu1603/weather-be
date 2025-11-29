#!/usr/bin/env python3
"""
Request Manager - Prevents server overload from concurrent heavy requests

Features:
1. Global Semaphore: Only 1 heavy task at a time (AI analysis, alerts refresh)
2. Queue info: Track what's running and waiting
3. Simple locking mechanism for heavy external API calls
"""
import threading
import time
from typing import Optional
from datetime import datetime


# ============== GLOBAL SEMAPHORE ==============
# This limits heavy tasks (DeepSeek AI, Open-Meteo fetch) to run one at a time
_global_semaphore = threading.Semaphore(1)
_current_task: Optional[str] = None
_current_task_lock = threading.Lock()


def acquire_heavy_task(task_name: str, timeout: float = 120.0) -> bool:
    """
    Acquire the global semaphore for a heavy task.

    Args:
        task_name: Name of the task (for logging)
        timeout: Max time to wait (seconds)

    Returns:
        True if acquired, False if timeout
    """
    global _current_task

    print(f"[RequestManager] {task_name} waiting for semaphore...")
    acquired = _global_semaphore.acquire(timeout=timeout)

    if acquired:
        with _current_task_lock:
            _current_task = task_name
        print(f"[RequestManager] {task_name} ACQUIRED semaphore")
    else:
        print(f"[RequestManager] {task_name} TIMEOUT waiting for semaphore")

    return acquired


def release_heavy_task(task_name: str):
    """
    Release the global semaphore after heavy task completes.

    Args:
        task_name: Name of the task (for logging)
    """
    global _current_task

    with _current_task_lock:
        _current_task = None

    _global_semaphore.release()
    print(f"[RequestManager] {task_name} RELEASED semaphore")


def get_current_task() -> Optional[str]:
    """Get the name of currently running heavy task"""
    with _current_task_lock:
        return _current_task


def is_semaphore_available() -> bool:
    """Check if semaphore is available (no heavy task running)"""
    # Try to acquire without blocking
    if _global_semaphore.acquire(blocking=False):
        _global_semaphore.release()
        return True
    return False


# ============== LEGACY CODE (keeping for compatibility) ==============
from enum import IntEnum
from typing import Dict, Callable, Any


class RequestPriority(IntEnum):
    """Request priority levels (higher = more important)"""
    LOW = 1       # Background refresh
    MEDIUM = 2    # Alerts loading
    HIGH = 3      # Region forecast (user action)
    CRITICAL = 4  # Manual refresh (user explicit action)


class RequestStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RequestManager:
    """
    Manages heavy API requests to prevent server overload.

    Usage:
        manager = RequestManager()

        # Start a heavy task
        request_id = manager.submit(
            name="region_forecast_CENTRAL",
            priority=RequestPriority.HIGH,
            task_fn=lambda: ai_service.analyze_forecast("CENTRAL", data),
            category="forecast"
        )

        # Check status
        status = manager.get_status(request_id)

        # Cancel if needed
        manager.cancel(request_id)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._semaphore = threading.Semaphore(1)  # Only 1 heavy task at a time
        self._requests: Dict[str, dict] = {}  # request_id -> request info
        self._current_request: Optional[str] = None
        self._request_lock = threading.Lock()
        self._request_counter = 0

        # Category locks - for cancelling same-category requests
        self._category_current: Dict[str, str] = {}  # category -> current request_id

        print("[RequestManager] Initialized with semaphore(1)")

    def submit(
        self,
        name: str,
        priority: RequestPriority,
        task_fn: Callable[[], Any],
        category: str = "default",
        timeout: float = 120.0
    ) -> str:
        """
        Submit a heavy task for execution.

        Args:
            name: Human-readable name for the request
            priority: Request priority level
            task_fn: Function to execute (must be callable with no args)
            category: Category for grouping (e.g., "forecast", "alerts")
            timeout: Maximum time to wait for semaphore (seconds)

        Returns:
            request_id: Unique identifier for this request
        """
        with self._request_lock:
            self._request_counter += 1
            request_id = f"req_{self._request_counter}_{int(time.time())}"

        request_info = {
            "id": request_id,
            "name": name,
            "priority": priority,
            "category": category,
            "status": RequestStatus.PENDING,
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "cancelled": threading.Event()
        }

        self._requests[request_id] = request_info

        print(f"[RequestManager] Submitted: {name} (id={request_id}, priority={priority.name}, category={category})")

        # Check if we should cancel existing same-category request
        self._handle_category_conflict(request_id, category, priority)

        # Start the task in a thread
        thread = threading.Thread(
            target=self._run_task,
            args=(request_id, task_fn, timeout),
            daemon=True
        )
        thread.start()

        return request_id

    def _handle_category_conflict(self, new_request_id: str, category: str, priority: RequestPriority):
        """Handle conflict when new request arrives in same category"""
        with self._request_lock:
            existing_id = self._category_current.get(category)

            if existing_id and existing_id in self._requests:
                existing = self._requests[existing_id]

                # If existing request is still pending/running and new has higher priority
                if existing["status"] in [RequestStatus.PENDING, RequestStatus.RUNNING]:
                    if priority > existing["priority"]:
                        print(f"[RequestManager] Cancelling {existing_id} (priority {existing['priority']}) for {new_request_id} (priority {priority})")
                        self._cancel_request(existing_id)

            # Set new request as current for this category
            self._category_current[category] = new_request_id

    def _run_task(self, request_id: str, task_fn: Callable, timeout: float):
        """Execute the task with semaphore control"""
        request = self._requests.get(request_id)
        if not request:
            return

        # Check if already cancelled
        if request["cancelled"].is_set():
            request["status"] = RequestStatus.CANCELLED
            print(f"[RequestManager] {request_id} cancelled before start")
            return

        # Try to acquire semaphore
        print(f"[RequestManager] {request_id} waiting for semaphore...")
        acquired = self._semaphore.acquire(timeout=timeout)

        if not acquired:
            request["status"] = RequestStatus.FAILED
            request["error"] = "Timeout waiting for semaphore"
            print(f"[RequestManager] {request_id} timeout waiting for semaphore")
            return

        # Check again if cancelled while waiting
        if request["cancelled"].is_set():
            self._semaphore.release()
            request["status"] = RequestStatus.CANCELLED
            print(f"[RequestManager] {request_id} cancelled while waiting")
            return

        try:
            request["status"] = RequestStatus.RUNNING
            request["started_at"] = datetime.now()
            self._current_request = request_id

            print(f"[RequestManager] {request_id} STARTED (acquired semaphore)")

            # Execute the task
            result = task_fn()

            # Check if cancelled during execution
            if request["cancelled"].is_set():
                request["status"] = RequestStatus.CANCELLED
                print(f"[RequestManager] {request_id} cancelled during execution")
            else:
                request["status"] = RequestStatus.COMPLETED
                request["result"] = result
                print(f"[RequestManager] {request_id} COMPLETED successfully")

        except Exception as e:
            request["status"] = RequestStatus.FAILED
            request["error"] = str(e)
            print(f"[RequestManager] {request_id} FAILED: {e}")

        finally:
            request["completed_at"] = datetime.now()
            self._current_request = None
            self._semaphore.release()
            print(f"[RequestManager] {request_id} released semaphore")

    def _cancel_request(self, request_id: str):
        """Mark a request as cancelled"""
        request = self._requests.get(request_id)
        if request:
            request["cancelled"].set()
            if request["status"] == RequestStatus.PENDING:
                request["status"] = RequestStatus.CANCELLED

    def cancel(self, request_id: str) -> bool:
        """
        Cancel a pending or running request.

        Args:
            request_id: The request to cancel

        Returns:
            True if request was cancelled, False if not found or already completed
        """
        request = self._requests.get(request_id)
        if not request:
            return False

        if request["status"] in [RequestStatus.COMPLETED, RequestStatus.CANCELLED]:
            return False

        self._cancel_request(request_id)
        print(f"[RequestManager] {request_id} cancel requested")
        return True

    def get_status(self, request_id: str) -> Optional[dict]:
        """
        Get status of a request.

        Returns:
            Dict with status info, or None if not found
        """
        request = self._requests.get(request_id)
        if not request:
            return None

        return {
            "id": request["id"],
            "name": request["name"],
            "status": request["status"],
            "priority": request["priority"].name,
            "category": request["category"],
            "created_at": request["created_at"].isoformat(),
            "started_at": request["started_at"].isoformat() if request["started_at"] else None,
            "completed_at": request["completed_at"].isoformat() if request["completed_at"] else None,
            "result": request["result"] if request["status"] == RequestStatus.COMPLETED else None,
            "error": request["error"] if request["status"] == RequestStatus.FAILED else None
        }

    def get_queue_info(self) -> dict:
        """Get information about the request queue"""
        pending = sum(1 for r in self._requests.values() if r["status"] == RequestStatus.PENDING)
        running = sum(1 for r in self._requests.values() if r["status"] == RequestStatus.RUNNING)

        return {
            "pending_count": pending,
            "running_count": running,
            "current_request": self._current_request,
            "semaphore_available": self._semaphore._value > 0
        }

    def is_cancelled(self, request_id: str) -> bool:
        """Check if a request has been cancelled"""
        request = self._requests.get(request_id)
        if not request:
            return False
        return request["cancelled"].is_set()

    def cleanup_old_requests(self, max_age_seconds: int = 3600):
        """Remove old completed/cancelled/failed requests"""
        now = datetime.now()
        to_remove = []

        for request_id, request in self._requests.items():
            if request["status"] in [RequestStatus.COMPLETED, RequestStatus.CANCELLED, RequestStatus.FAILED]:
                if request["completed_at"]:
                    age = (now - request["completed_at"]).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(request_id)

        for request_id in to_remove:
            del self._requests[request_id]

        if to_remove:
            print(f"[RequestManager] Cleaned up {len(to_remove)} old requests")


# Singleton instance
request_manager = RequestManager()
