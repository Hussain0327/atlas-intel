"""Prometheus custom metrics for Atlas Intel."""

from prometheus_client import Counter

sync_operations_total = Counter(
    "atlas_sync_operations_total",
    "Total sync operations by type and status",
    ["sync_type", "status"],
)

cache_hits_total = Counter(
    "atlas_cache_hits_total",
    "Total cache hits",
    ["cache_name"],
)

cache_misses_total = Counter(
    "atlas_cache_misses_total",
    "Total cache misses",
    ["cache_name"],
)

llm_requests_total = Counter(
    "atlas_llm_requests_total",
    "Total LLM provider requests",
    ["provider", "operation", "status"],
)
