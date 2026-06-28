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
        """
        Initialize the BatchSizeAdapter.
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

    def __repr__(self) -> str:
        return f"BatchSizeAdapter(size={self.current_size}, rate={self.success_rate():.2f}, trend={self.trend}, window={len(self.outcomes)}/{self.window_size}, min={self.min_size}, max={self.max_size}, threshold={self.success_threshold})"

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

    def recommended_size(self) -> int:
        return self.current_size

    def record_outcome(self, success_ratio: float) -> None:
        normalized = max(0.0, min(1.0, success_ratio))
        success = normalized >= self.success_threshold
        self.outcomes.append(success)
        while len(self.outcomes) > self.window_size:
            self.outcomes.popleft()
        self._adjust_size()

    def reset(self) -> None:
        """Resets the adapter to its initial state."""
        self.outcomes.clear()
        self.current_size = self.initial_size

    def success_rate(self) -> float:
        if not self.outcomes:
            return 1.0
        return sum(1 for ok in self.outcomes if ok) / len(self.outcomes)

    def _adjust_size(self) -> None:
        rate = self.success_rate()
        if rate < self.low_threshold:
            self.current_size = max(self.min_size, (self.current_size * 2) // 3)
        elif rate > self.high_threshold:
            self.current_size = min(self.max_size, (self.current_size * 3) // 2)
