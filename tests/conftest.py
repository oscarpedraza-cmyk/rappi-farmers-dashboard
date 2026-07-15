"""Shared pytest fixtures and path setup for the test suite.

Ensures the project root is importable so ``import core.xxx`` works when pytest
is invoked from anywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
