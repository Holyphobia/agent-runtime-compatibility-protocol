"""Minimal semver range matching for ARCP compatibility resolution."""

from __future__ import annotations

import re
from typing import Sequence

VersionTuple = tuple[int, ...]

_CONSTRAINT_RE = re.compile(r"^(>=|<=|>|<|=)?\s*(\d[\d.]*)$")


def parse_version(v: str) -> VersionTuple:
    """Parse a dotted version string into a tuple of ints.

    >>> parse_version("1.3.2")
    (1, 3, 2)
    >>> parse_version("0.1")
    (0, 1)
    """
    return tuple(int(p) for p in v.split("."))


def _pad(t: VersionTuple, length: int) -> VersionTuple:
    if len(t) < length:
        return t + (0,) * (length - len(t))
    return t


def _normalize(a: VersionTuple, b: VersionTuple) -> tuple[VersionTuple, VersionTuple]:
    m = max(len(a), len(b))
    return _pad(a, m), _pad(b, m)


def _parse_single_constraint(s: str) -> tuple[str, VersionTuple]:
    m = _CONSTRAINT_RE.match(s.strip())
    if not m:
        raise ValueError(f"Invalid version constraint: {s!r}")
    op = m.group(1) or "="
    ver = parse_version(m.group(2))
    return op, ver


def match_range(range_str: str, version_str: str) -> bool:
    """Return True if *version_str* satisfies *range_str*.

    Supports:
      - Simple/pinned version: ``"0.1"`` → exact match (after normalization)
      - Comma-separated constraints: ``">=1.3.2,<2.0.0"``

    >>> match_range(">=1.3.2,<2.0.0", "1.3.2")
    True
    >>> match_range(">=1.3.2,<2.0.0", "2.0.0")
    False
    >>> match_range("0.1", "0.1")
    True
    >>> match_range("0.1", "0.1.0")
    True
    >>> match_range(">=0.1.0,<0.2.0", "0.1.0")
    True
    >>> match_range(">=0.1.0,<0.2.0", "0.2.0")
    False
    """
    range_str = range_str.strip()
    version_str = version_str.strip()

    # Simple literal (no operators or commas) → exact/pinned match
    if not any(op in range_str for op in (">=", "<=", ">", "<", "=", "^", "~", ",")):
        return _pad(parse_version(range_str), 3) == _pad(parse_version(version_str), 3)

    parts = [p.strip() for p in range_str.split(",")]
    try:
        constraints = [_parse_single_constraint(p) for p in parts]
    except ValueError:
        return False

    ver = parse_version(version_str)

    for op, target in constraints:
        a, b = _normalize(ver, target)
        if op == ">=":
            if not (a >= b):
                return False
        elif op == "<=":
            if not (a <= b):
                return False
        elif op == ">":
            if not (a > b):
                return False
        elif op == "<":
            if not (a < b):
                return False
        elif op == "=":
            if not (a == b):
                return False
    return True


def is_broad_range(range_str: str) -> bool:
    """Heuristic: a range is considered broad if it spans ≥ 2 major versions."""
    range_str = range_str.strip()
    if "," not in range_str:
        return False
    parts = [p.strip() for p in range_str.split(",")]
    try:
        constraints = [_parse_single_constraint(p) for p in parts]
    except ValueError:
        return False

    lower_major: int | None = None
    upper_major: int | None = None

    for op, ver in constraints:
        if op in (">=", ">"):
            lower_major = ver[0] if ver else None
        elif op in ("<=", "<"):
            # For "<X.Y.Z", the upper exclusive bound is X
            upper_major = ver[0] if ver else None

    if lower_major is not None and upper_major is not None:
        return (upper_major - lower_major) >= 2
    return False
