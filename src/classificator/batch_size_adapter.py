from __future__ import annotations

from collections import deque


class BatchSizeAdapter:
    def __init__(
        self,
        initial_size: int,
        min_size: int = 3,
        window_size: int = 10,
        success_threshold: float = 0.9,
        max_size: int = None,
        low_threshold: float = 0.5,
        high_threshold: float = 0.9,
    ) -> None:
        """Initialize the BatchSizeAdapter.

        Two distinct thresholds serve different purposes and should not be confused:

        * ``success_threshold`` — used by :meth:`record_outcome` to classify an individual
          success ratio as a binary outcome (True/False). Defaults to 0.9.
        * ``low_threshold`` / ``high_threshold`` — used by :attr:`trend` and :meth:`_adjust_size`
          to decide whether the window-level success rate indicates a stable, increasing, or
          decreasing trend that warrants adjusting ``current_size``. The default range [0.5, 0.9]
          leaves a ~40 pp "stable" band between them.

        These two threshold groups are independent — ``success_threshold`` may sit inside, outside,
        or overlap the adjustment range without conflict.
        """
        if initial_size < min_size:
            raise ValueError("initial_size must be >= min_size")
        if min_size < 1:
            raise ValueError("min_size must be >= 1")
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        if max_size is not None and max_size < initial_size:
            raise ValueError("max_size must be >= initial_size")
        if not (0.0 <= success_threshold <= 1.0):
            raise ValueError("success_threshold must be between 0.0 and 1.0")
        if not (0.0 <= low_threshold <= 1.0):
            raise ValueError("low_threshold must be between 0.0 and 1.0")
        if not (0.0 <= high_threshold <= 1.0):
            raise ValueError("high_threshold must be between 0.0 and 1.0")
        if low_threshold >= high_threshold:
            raise ValueError("low_threshold must be < high_threshold")
        self.initial_size = initial_size
        self.min_size = min_size
        self.window_size = window_size
        self.success_threshold = success_threshold
        self.max_size = max_size if max_size is not None else initial_size
        self.current_size = initial_size
        self.outcomes: deque[bool] = deque()
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.step_count = 0
        self.total_records = 0
        self._size_changes: list[tuple[int, int]] = [(0, initial_size)]

    def __repr__(self) -> str:
        return f"BatchSizeAdapter(size={self.current_size}, rate={self.success_rate():.2f}, trend={self.trend}, window={len(self.outcomes)}/{self.window_size}, min={self.min_size}, max={self.max_size}, threshold={self.success_threshold})"

    def __str__(self) -> str:
        return (
            f"BatchSizeAdapter(size={self.current_size}, "
            f"trend={self.trend}, "
            f"success_rate={self.success_rate():.0%})"
        )

    def __len__(self) -> int:
        return len(self.outcomes)

    def __iter__(self):
        return iter(self.outcomes)

    @property
    def trend(self) -> str:
        rate = self.success_rate()
        if rate < self.low_threshold:
            return "decreasing"
        if rate > self.high_threshold:
            return "increasing"
        return "stable"

    @property
    def is_stable(self) -> bool:
        return self.trend == "stable"

    @property
    def is_converged(self) -> bool:
        return self.is_stable and len(self.outcomes) == self.window_size

    def get_metrics(self) -> dict[str, float | str | int]:
        return {
            "current_size": self.current_size,
            "success_rate": self.success_rate(),
            "trend": self.trend,
            "is_stable": self.is_stable,
            "is_converged": self.is_converged,
            "window_usage": len(self.outcomes),
            "window_size": self.window_size,
            "step_count": self.step_count,
            "total_records": self.total_records,
        }

    def recommended_size(self) -> int:
        return self.current_size

    def size_history(self) -> list[tuple[int, int]]:
        """Return a log of (step_number, current_size) snapshots.

        Captures every recorded adjustment including the initial state at step 0.
        Useful for debugging convergence behavior over time.
        """
        return list(self._size_changes)

    def record_outcome(self, success_ratio: float) -> None:
        normalized = max(0.0, min(1.0, success_ratio))
        success = normalized >= self.success_threshold
        self.outcomes.append(success)
        while len(self.outcomes) > self.window_size:
            self.outcomes.popleft()
        self.step_count += 1
        self._adjust_size()

    def reset(self) -> None:
        """Resets the adapter to its initial state."""
        self.outcomes.clear()
        self.current_size = self.initial_size
        self.step_count = 0
        self.total_records = 0
        self._size_changes = [(0, self.initial_size)]

    def success_rate(self) -> float:
        if not self.outcomes:
            return 1.0
        return sum(1 for ok in self.outcomes if ok) / len(self.outcomes)

    def history(self) -> list[bool]:
        """Return outcomes as a plain list (newest last)."""
        return list(self.outcomes)

    def _adjust_size(self) -> None:
        rate = self.success_rate()
        old_size = self.current_size
        self.total_records += 1
        if rate < self.low_threshold:
            self.current_size = max(self.min_size, (self.current_size * 2) // 3)
        elif rate > self.high_threshold:
            self.current_size = min(self.max_size, (self.current_size * 3) // 2)
        else:
            return
        if self.current_size != old_size:
            self._size_changes.append((self.step_count, self.current_size))
