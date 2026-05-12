"""Compatibility shim for legacy snapshot imports."""

from .legacy.snapshot_data import (
    SnapshotFetchResult,
    fetch_current_energy_snapshot,
)

__all__ = ["SnapshotFetchResult", "fetch_current_energy_snapshot"]
