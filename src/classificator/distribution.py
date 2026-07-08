from __future__ import annotations


class RarityDistribution:
    def __init__(self) -> None:
        self._counts = [0, 0, 0, 0, 0, 0]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RarityDistribution):
            return False
        return self._counts == other._counts

    def __repr__(self) -> str:
        return f"RarityDistribution(counts={self._counts[1:]})"

    @classmethod
    def from_levels(cls, levels: list[int] | tuple[int, ...] | set[int]) -> "RarityDistribution":
        d = cls()
        for level in levels:
            d.increment(level)
        return d

    @staticmethod
    def _validate_level(level: int) -> None:
        if not (1 <= level <= 5):
            raise ValueError(f"Level must be in range 1..5, got {level}")

    def increment(self, level: int) -> None:
        self._validate_level(level)
        self._counts[level] += 1

    def set_level(self, previous_level: int | None, new_level: int) -> None:
        if previous_level is not None:
            self._validate_level(previous_level)
            if self._counts[previous_level] > 0:
                self._counts[previous_level] -= 1
        self._validate_level(new_level)
        self._counts[new_level] += 1

    def count(self, level: int) -> int:
        self._validate_level(level)
        return self._counts[level]

    @property
    def total(self) -> int:
        return sum(self._counts[1:6])

    def format(self) -> str:
        total = self.total
        parts = []
        for level in range(1, 6):
            count = self._counts[level]
            pct = (count * 100.0 / total) if total > 0 else 0.0
            parts.append(f"{level}:{count}({pct:.1f}%)")
        return f"distribution=[{' '.join(parts)}]"
