"""T11 — retention TTL jobs & metrics export (V1_TECHNICAL_PLAN §12, §13 T11).

Live acceptance specs that skip until retention.py / the metrics export land.
Both are wired around the DB session, so the deeper TTL-deletes-aged-row check
is added once the cleanup entry point is known; this pins its surface.
"""


def test_retention_exposes_a_cleanup_entry_point(callable_or_skip) -> None:
    cleanup = callable_or_skip(
        "app.data.retention",
        "run_retention",
        "run_cleanup",
        "cleanup_expired",
        "purge_expired",
        "cleanup",
    )
    assert callable(cleanup)


def test_metrics_export_exists(callable_or_skip) -> None:
    metrics = callable_or_skip(
        "app.obs.metrics",
        "export_metrics",
        "collect_metrics",
        "metrics_summary",
        "aggregate",
    )
    assert callable(metrics)
