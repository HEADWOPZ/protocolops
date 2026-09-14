from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward from *start* (or cwd) looking for pyproject + fixtures."""
    here = (start or Path.cwd()).resolve()
    candidates = [here, *here.parents]
    for path in candidates:
        if (path / "pyproject.toml").is_file() and (path / "fixtures").is_dir():
            return path
    package_root = Path(__file__).resolve().parents[2]
    if (package_root / "fixtures").is_dir():
        return package_root
    return here


def resolve_path(value: str | Path, *, root: Path | None = None) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return ((root or find_repo_root()) / path).resolve()
