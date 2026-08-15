from __future__ import annotations

from datetime import datetime, timezone
from random import Random

from wrapper.annotate_versions import AnnotatedEvent, AnnotatedTrace
from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig
from wrapper.enrichment import EnrichmentConfig, enrich_traces


def test_given_enriched_trace_when_inspected_then_lifecycle_pairs_share_instance_and_resource():
    enriched = enrich_traces(
        traces=(_trace("v1", 0, ("A",)),),
        snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),),
        config=_config(assign_enabled=False, pool_size=2),
        rng=Random(11),
    )

    instance = enriched.traces[0].instances[0]

    assert [event.transition for event in instance.events] == ["start", "complete"]
    assert {event.instance_id for event in instance.events} == {instance.instance_id}
    assert {event.resource for event in instance.events} == {instance.resource}
    assert {event.activity for event in instance.events} == {"A"}


def test_given_assign_enabled_when_enriched_then_assign_event_precedes_start_and_complete():
    enriched = enrich_traces(
        traces=(_trace("v1", 0, ("A",)),),
        snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),),
        config=_config(assign_enabled=True),
        rng=Random(11),
    )

    assert [event.transition for event in enriched.traces[0].instances[0].events] == [
        "assign",
        "start",
        "complete",
    ]


def test_given_same_activity_across_versions_when_enriched_then_resource_pool_is_stable():
    enriched = enrich_traces(
        traces=(
            _trace("v1", 0, ("A",)),
            _trace("v2", 1, ("A",)),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),
            ProcessTreeSnapshot(version_id="v2", process_tree="'A'"),
        ),
        config=_config(pool_size=2),
        rng=Random(11),
    )

    assert enriched.resource_pools["A"] == ("resource_a_001", "resource_a_002")
    assert {trace.instances[0].resource for trace in enriched.traces} <= set(enriched.resource_pools["A"])


def test_given_single_resource_when_two_cases_overlap_then_scheduler_prevents_double_booking():
    enriched = enrich_traces(
        traces=(
            _trace("v1", 0, ("A",)),
            _trace("v1", 1, ("A",)),
        ),
        snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),),
        config=_config(pool_size=1, arrival_rate=100.0, duration_mu=0.0, duration_sigma=0.0),
        rng=Random(3),
    )

    first = enriched.traces[0].instances[0]
    second = enriched.traces[1].instances[0]

    assert first.resource == second.resource
    assert first.complete_at <= second.start_at


def test_given_later_version_activates_before_prior_case_completes_then_carryover_is_reported():
    enriched = enrich_traces(
        traces=(
            _trace("v1", 0, ("A",)),
            _trace("v2", 1, ("B",)),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),
            ProcessTreeSnapshot(version_id="v2", process_tree="'B'"),
        ),
        config=_config(arrival_rate=100.0, duration_mu=1.0, duration_sigma=0.0),
        rng=Random(5),
    )

    assert enriched.version_activation_times["v1"] <= enriched.version_activation_times["v2"]
    assert enriched.carryover_summary["plus_1"] == 1


def _trace(version_id: str, source_index: int, activities: tuple[str, ...]) -> AnnotatedTrace:
    return AnnotatedTrace(
        source_index=source_index,
        attributes={"concept:version": version_id},
        events=tuple(AnnotatedEvent(attributes={"concept:name": activity}) for activity in activities),
    )


def _config(
    *,
    assign_enabled: bool = False,
    pool_size: int = 3,
    arrival_rate: float = 1.0,
    duration_mu: float = -2.0,
    duration_sigma: float = 0.1,
) -> EnrichmentConfig:
    return EnrichmentConfig(
        lifecycle=LifecycleConfig(assign_enabled=assign_enabled),
        resources=ResourceConfig(pool_size=pool_size),
        temporal=TemporalConfig(
            arrival_rate=arrival_rate,
            duration_mu=duration_mu,
            duration_sigma=duration_sigma,
            epoch=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    )
