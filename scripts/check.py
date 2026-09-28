"""Single offline verification entrypoint for developers, CI and automation."""
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for command in [
        [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts/check.py"],
        [sys.executable, "-m", "pytest", "-q"],
    ]:
        print("+ " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
