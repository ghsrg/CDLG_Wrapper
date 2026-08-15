from __future__ import annotations

from datetime import datetime, timezone
from random import Random

import pytest

from wrapper.annotate_versions import AnnotatedEvent, AnnotatedTrace
from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig
from wrapper.enrichment import EnrichmentConfig, enrich_traces
from wrapper.errors import ArtifactError


def test_given_parallel_tree_when_enriched_then_parallel_activities_overlap():
    enriched = enrich_traces(
        traces=(
            _trace(version_id="v1", source_index=0, activities=("A", "B")),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="+('A','B')"),
        ),
        config=_config(duration_mu=0.0, duration_sigma=0.0),
        rng=Random(7),
    )

    a = _instance(enriched.traces[0], "A")
    b = _instance(enriched.traces[0], "B")

    assert a.start_at == b.start_at
    assert a.complete_at == b.complete_at


def test_given_sequence_tree_when_enriched_then_activity_order_is_preserved_without_overlap():
    enriched = enrich_traces(
        traces=(
            _trace(version_id="v1", source_index=0, activities=("A", "B")),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="->('A','B')"),
        ),
        config=_config(duration_mu=0.0, duration_sigma=0.0),
        rng=Random(7),
    )

    instances = enriched.traces[0].instances

    assert [item.activity for item in instances] == ["A", "B"]
    assert instances[0].complete_at <= instances[1].start_at


def test_given_nested_parallel_tree_when_enriched_then_parallel_branch_activities_overlap_after_prefix():
    enriched = enrich_traces(
        traces=(
            _trace(version_id="v1", source_index=0, activities=("A", "B", "C")),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="->('A',+('B','C'))"),
        ),
        config=_config(duration_mu=0.0, duration_sigma=0.0),
        rng=Random(7),
    )

    a = _instance(enriched.traces[0], "A")
    b = _instance(enriched.traces[0], "B")
    c = _instance(enriched.traces[0], "C")

    assert a.complete_at <= b.start_at
    assert b.start_at == c.start_at
    assert b.complete_at == c.complete_at


def test_given_xor_tree_when_enriched_then_cdlg_selected_branch_is_retained():
    enriched = enrich_traces(
        traces=(
            _trace(version_id="v1", source_index=0, activities=("B",)),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="X('A','B')"),
        ),
        config=_config(),
        rng=Random(7),
    )

    assert [item.activity for item in enriched.traces[0].instances] == ["B"]


def test_given_loop_tree_when_enriched_then_repeated_activity_occurrences_are_retained():
    enriched = enrich_traces(
        traces=(
            _trace(version_id="v1", source_index=0, activities=("A", "B", "A")),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="*('A','B')"),
        ),
        config=_config(),
        rng=Random(7),
    )

    assert [item.activity for item in enriched.traces[0].instances] == ["A", "B", "A"]


def test_given_trace_activity_absent_from_tree_when_enriched_then_artifact_error_is_raised():
    with pytest.raises(ArtifactError, match="cannot be replayed"):
        enrich_traces(
            traces=(
                _trace(version_id="v1", source_index=0, activities=("A", "C")),
            ),
            snapshots=(
                ProcessTreeSnapshot(version_id="v1", process_tree="->('A','B')"),
            ),
            config=_config(),
            rng=Random(7),
        )


def _trace(*, version_id: str, source_index: int, activities: tuple[str, ...]) -> AnnotatedTrace:
    return AnnotatedTrace(
        source_index=source_index,
        attributes={"concept:version": version_id},
        events=tuple(AnnotatedEvent(attributes={"concept:name": activity}) for activity in activities),
    )


def _config(*, duration_mu: float = -2.0, duration_sigma: float = 0.1) -> EnrichmentConfig:
    return EnrichmentConfig(
        lifecycle=LifecycleConfig(assign_enabled=False),
        resources=ResourceConfig(pool_size=3),
        temporal=TemporalConfig(
            arrival_rate=1.0,
            duration_mu=duration_mu,
            duration_sigma=duration_sigma,
            epoch=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    )


def _instance(trace, activity):
    return next(item for item in trace.instances if item.activity == activity)
