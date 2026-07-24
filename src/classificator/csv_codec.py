from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path


class CsvFormatError(RuntimeError):
    pass


@dataclass(frozen=True)
class CsvRecord:
    line_number: int
    values: list[str]


@dataclass(frozen=True)
class CsvTable:
    headers: list[str]
    records: list[CsvRecord]


class CsvCodec:
    def _validate_headers(self, headers: list[str]) -> None:
        if not headers:
            raise CsvFormatError("write_table received empty headers")
        for i, cell in enumerate(headers):
            if not str(cell).strip():
                raise CsvFormatError(
                    f"write_table header column {i + 1} is empty"
                )

    def read_table(self, path: Path) -> CsvTable:
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)

        if not rows:
            raise CsvFormatError(f"CSV file is empty: {path}")

        headers = [str(x) for x in rows[0]]
        if not headers:
            raise CsvFormatError(f"CSV has empty header row: {path}")
        for i, cell in enumerate(headers):
            if not cell.strip():
                raise CsvFormatError(
                    f"CSV {path} header column {i + 1} is empty"
                )

        records: list[CsvRecord] = []
        for i, row in enumerate(rows[1:], start=2):
            if len(row) == 1 and row[0] == "":
                continue
            if len(row) != len(headers):
                raise CsvFormatError(
                    f"CSV {path} line {i} has {len(row)} columns, expected {len(headers)}"
                )
            records.append(CsvRecord(line_number=i, values=[str(x) for x in row]))

        return CsvTable(headers=headers, records=records)

    def _ensure_dir(self, path: Path) -> None:
        """Create the parent directory of `path` if it does not already exist."""
        path.parent.mkdir(parents=True, exist_ok=True)

    def write_table(self, path: Path, headers: list[str], rows: list[list[str]]) -> None:
        self._ensure_dir(path)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            for row in rows:
                if len(row) != len(headers):
                    raise CsvFormatError(
                        f"Attempted to write {len(row)} columns, expected {len(headers)}"
                    )
                writer.writerow(row)

    def write_table_atomic(self, path: Path, headers: list[str], rows: list[list[str]]) -> None:
        tmp = path.with_name(f"{path.name}.tmp")
        self.write_table(tmp, headers, rows)
        os.replace(tmp, path)
