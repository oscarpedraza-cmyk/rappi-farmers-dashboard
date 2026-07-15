"""Centralized configuration for the Rappi Farmers Dashboard.

All values that used to live as scattered module-level constants (team roster,
scoring weights/thresholds, storage identifiers) are defined here so there is a
single source of truth. The original modules (``core.loader``, ``core.metrics``,
``core.db``, ``core.auth``) re-export these names to preserve their public API.

Sub-modules
-----------
- :mod:`config.team`    — roster, names, Slack IDs, supervisor identity.
- :mod:`config.scoring` — compensation weights, bounds and semaphore thresholds.
- :mod:`config.storage` — SQLite / Google Sheets identifiers and limits.
"""
from __future__ import annotations
