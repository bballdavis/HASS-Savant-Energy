"""Current-mode Influx client export shim."""

from ..influx_client import InfluxFetchResult, fetch_influx_snapshot

__all__ = ["InfluxFetchResult", "fetch_influx_snapshot"]
