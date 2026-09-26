from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ResolutionStatus(Enum):
    """Outcome categories for a symlink resolution attempt.

    We use an enum rather than magic strings so callers can match exhaustively
    without typos. Order matters only for readability; no logic depends on it.
    """
    EXISTS = "exists"
    MISSING = "missing"
    CIRCULAR = "circular"
    TOO_DEEP = "too_deep"


@dataclass(frozen=True)
class ResolutionResult:
    """Result of resolving a possibly-symlinked path.

    `path` is the final path we reached (existing target if resolved, last
    link if we bailed out). `chain` is the ordered list of paths visited,
    including the start and every link followed. `jump_count` excludes the
    starting path so it's the number of actual link traversals.
    """
    status: ResolutionStatus
    path: str
    chain: tuple
    jump_count: int

    def __post_init__(self):
        # Normalize chain to a tuple so callers get a hashable, immutable value
        # regardless of how they constructed the input.
        object.__setattr__(self, "chain", tuple(self.chain))


def _norm(p: Path | str) -> str:
    """Stringify and os.path.normpath the input for consistent comparisons."""
    return os.path.normpath(str(p))


def resolve(path: str | Path, max_depth: int = 40) -> ResolutionResult:
    """Resolve a symlink chain, reporting status at each step.

    Walks symlinks one at a time using os.readlink so we can detect cycles by
    tracking visited paths and bail out at exactly max_depth jumps (default 40,
    matching POSIX's SYMLOOP_MAX upper bound of 40 in modern glibc).

    Returns EXISTS only when the final resolved path is a real file/dir, not
    itself a symlink. Returns MISSING when the chain ends at a nonexistent path.
    Returns CIRCULAR if we revisit a path already in our chain. Returns
    TOO_DEEP if we would exceed max_depth jumps without resolving.

    Relative symlinks are resolved relative to the directory of the link that
    contains them, which is how readlink results must be interpreted.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    current = _norm(path)
    visited = [current]
    jumps = 0

    while True:
        if not os.path.islink(current):
            status = ResolutionStatus.EXISTS if os.path.exists(current) else ResolutionStatus.MISSING
            return ResolutionResult(status, current, tuple(visited), jumps)

        if jumps >= max_depth:
            return ResolutionResult(ResolutionStatus.TOO_DEEP, current, tuple(visited), jumps)

        target_raw = os.readlink(current)
        # readlink returns the raw link text; relative links are relative to
        # the directory containing the link, not the cwd.
        if os.path.isabs(target_raw):
            nxt = _norm(target_raw)
        else:
            nxt = _norm(os.path.join(os.path.dirname(current), target_raw))

        if nxt in visited:
            return ResolutionResult(ResolutionStatus.CIRCULAR, nxt, tuple(visited + [nxt]), jumps + 1)

        visited.append(nxt)
        jumps += 1
        current = nxt
