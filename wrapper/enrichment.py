from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random

from wrapper.annotate_versions import AnnotatedTrace
from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig
from wrapper.errors import ArtifactError
from wrapper.structure import TreeNode, _parse_tree_string, _visible_labels


@dataclass(frozen=True)
class EnrichmentConfig:
    lifecycle: LifecycleConfig
    resources: ResourceConfig
    temporal: TemporalConfig


@dataclass(frozen=True)
class EnrichedEvent:
    activity: str
    transition: str
    timestamp: datetime
    resource: str
    instance_id: str
    version_id: str


@dataclass(frozen=True)
class EnrichedActivityInstance:
    activity: str
    occurrence_index: int
    instance_id: str
    resource: str
    start_at: datetime
    complete_at: datetime
    events: tuple[EnrichedEvent, ...]


@dataclass(frozen=True)
class EnrichedTrace:
    source_index: int
    case_id: str
    version_id: str
    arrival_at: datetime
    complete_at: datetime
    attributes: dict[str, str]
    instances: tuple[EnrichedActivityInstance, ...]


@dataclass(frozen=True)
class EnrichedLog:
    traces: tuple[EnrichedTrace, ...]
    resource_pools: dict[str, tuple[str, ...]]
    version_activation_times: dict[str, datetime]
    carryover_summary: dict[str, int]


@dataclass
class _ResourceState:
    resource_id: str
    available_at: datetime
    workload_seconds: float = 0.0


def enrich_traces(
    *,
    traces: tuple[AnnotatedTrace, ...],
    snapshots: tuple[ProcessTreeSnapshot, ...],
    config: EnrichmentConfig,
    rng: Random | None = None,
) -> EnrichedLog:
    random_source = rng if rng is not None else Random(0)
    trees = {snapshot.version_id: _parse_tree_string(snapshot.process_tree) for snapshot in snapshots}
    resource_pools = _build_resource_pools(trees, config.resources.pool_size)
    resource_states = {
        activity: [_ResourceState(resource_id=resource, available_at=config.temporal.epoch) for resource in pool]
        for activity, pool in resource_pools.items()
    }

    enriched_traces: list[EnrichedTrace] = []
    version_activation_times: dict[str, datetime] = {}
    current_arrival = config.temporal.epoch

    for trace_index, trace in enumerate(traces, start=1):
        version_id = _version_id(trace)
        if version_id not in trees:
            raise ArtifactError(f"missing process tree snapshot for {version_id}")
        if trace_index > 1:
            current_arrival += timedelta(seconds=random_source.expovariate(config.temporal.arrival_rate))
        version_activation_times.setdefault(version_id, current_arrival)
        labels = _activity_labels(trace)
        try:
            _validate_trace(labels, trees[version_id], version_id)
            instances = _schedule_trace(
                labels=labels,
                version_id=version_id,
                case_id=f"case_{trace_index:06d}",
                root=trees[version_id],
                arrival_at=current_arrival,
                config=config,
                resource_states=resource_states,
                rng=random_source,
            )
        except ArtifactError:
            _validate_trace_labels_known(labels, trees[version_id], version_id)
            instances = _schedule_observed_order_trace(
                labels=labels,
                version_id=version_id,
                case_id=f"case_{trace_index:06d}",
                arrival_at=current_arrival,
                config=config,
                resource_states=resource_states,
                rng=random_source,
            )
        complete_at = max((item.complete_at for item in instances), default=current_arrival)
        enriched_traces.append(
            EnrichedTrace(
                source_index=trace.source_index,
                case_id=f"case_{trace_index:06d}",
                version_id=version_id,
                arrival_at=current_arrival,
                complete_at=complete_at,
                attributes=dict(trace.attributes),
                instances=tuple(instances),
            )
        )

    return EnrichedLog(
        traces=tuple(enriched_traces),
        resource_pools=resource_pools,
        version_activation_times=version_activation_times,
        carryover_summary=_carryover_summary(enriched_traces, version_activation_times),
    )


def _schedule_trace(
    *,
    labels: tuple[str, ...],
    version_id: str,
    case_id: str,
    root: TreeNode,
    arrival_at: datetime,
    config: EnrichmentConfig,
    resource_states: dict[str, list[_ResourceState]],
    rng: Random,
) -> list[EnrichedActivityInstance]:
    occurrence_counts: Counter[str] = Counter()
    instances, next_position, _ = _schedule_node(
        root=root,
        labels=labels,
        position=0,
        version_id=version_id,
        case_id=case_id,
        earliest_start=arrival_at,
        config=config,
        resource_states=resource_states,
        occurrence_counts=occurrence_counts,
        rng=rng,
    )
    if next_position != len(labels):
        raise ArtifactError(f"trace cannot be replayed against {version_id}")
    return instances


def _schedule_observed_order_trace(
    *,
    labels: tuple[str, ...],
    version_id: str,
    case_id: str,
    arrival_at: datetime,
    config: EnrichmentConfig,
    resource_states: dict[str, list[_ResourceState]],
    rng: Random,
) -> list[EnrichedActivityInstance]:
    occurrence_counts: Counter[str] = Counter()
    instances: list[EnrichedActivityInstance] = []
    next_start = arrival_at
    for activity in labels:
        instance = _schedule_activity(
            activity=activity,
            version_id=version_id,
            case_id=case_id,
            earliest_start=next_start,
            config=config,
            resource_states=resource_states,
            occurrence_counts=occurrence_counts,
            rng=rng,
        )
        instances.append(instance)
        next_start = instance.complete_at
    return instances


def _schedule_node(
    *,
    root: TreeNode,
    labels: tuple[str, ...],
    position: int,
    version_id: str,
    case_id: str,
    earliest_start: datetime,
    config: EnrichmentConfig,
    resource_states: dict[str, list[_ResourceState]],
    occurrence_counts: Counter[str],
    rng: Random,
) -> tuple[list[EnrichedActivityInstance], int, datetime]:
    if root.operator == "tau":
        return [], position, earliest_start

    if root.label is not None:
        if position >= len(labels) or labels[position] != root.label:
            raise ArtifactError(f"trace cannot be replayed against {version_id}")
        instance = _schedule_activity(
            activity=root.label,
            version_id=version_id,
            case_id=case_id,
            earliest_start=earliest_start,
            config=config,
            resource_states=resource_states,
            occurrence_counts=occurrence_counts,
            rng=rng,
        )
        return [instance], position + 1, instance.complete_at

    if root.operator == "+":
        branch_instances: list[EnrichedActivityInstance] = []
        next_position = position
        complete_at = earliest_start
        for child in root.children:
            child_instances, next_position, child_complete_at = _schedule_node(
                root=child,
                labels=labels,
                position=next_position,
                version_id=version_id,
                case_id=case_id,
                earliest_start=earliest_start,
                config=config,
                resource_states=resource_states,
                occurrence_counts=occurrence_counts,
                rng=rng,
            )
            branch_instances.extend(child_instances)
            complete_at = max(complete_at, child_complete_at)
        return branch_instances, next_position, complete_at

    if root.operator == "X":
        for child in root.children:
            child_labels = tuple(_visible_labels(child))
            if labels[position : position + len(child_labels)] == child_labels:
                return _schedule_node(
                    root=child,
                    labels=labels,
                    position=position,
                    version_id=version_id,
                    case_id=case_id,
                    earliest_start=earliest_start,
                    config=config,
                    resource_states=resource_states,
                    occurrence_counts=occurrence_counts,
                    rng=rng,
                )
        raise ArtifactError(f"trace cannot be replayed against {version_id}")

    if root.operator == "*":
        allowed = set(_visible_labels(root))
        instances: list[EnrichedActivityInstance] = []
        next_position = position
        next_start = earliest_start
        complete_at = earliest_start
        while next_position < len(labels) and labels[next_position] in allowed:
            activity = labels[next_position]
            instance = _schedule_activity(
                activity=activity,
                version_id=version_id,
                case_id=case_id,
                earliest_start=next_start,
                config=config,
                resource_states=resource_states,
                occurrence_counts=occurrence_counts,
                rng=rng,
            )
            instances.append(instance)
            next_position += 1
            complete_at = instance.complete_at
            next_start = complete_at
        if next_position == position:
            raise ArtifactError(f"trace cannot be replayed against {version_id}")
        return instances, next_position, complete_at

    instances: list[EnrichedActivityInstance] = []
    next_position = position
    next_start = earliest_start
    complete_at = earliest_start
    for child in root.children:
        child_instances, next_position, complete_at = _schedule_node(
            root=child,
            labels=labels,
            position=next_position,
            version_id=version_id,
            case_id=case_id,
            earliest_start=next_start,
            config=config,
            resource_states=resource_states,
            occurrence_counts=occurrence_counts,
            rng=rng,
        )
        instances.extend(child_instances)
        next_start = complete_at
    return instances, next_position, complete_at


def _schedule_activity(
    *,
    activity: str,
    version_id: str,
    case_id: str,
    earliest_start: datetime,
    config: EnrichmentConfig,
    resource_states: dict[str, list[_ResourceState]],
    occurrence_counts: Counter[str],
    rng: Random,
) -> EnrichedActivityInstance:
    occurrence_counts[activity] += 1
    duration = timedelta(seconds=max(rng.lognormvariate(config.temporal.duration_mu, config.temporal.duration_sigma), 0.001))
    resource_state = _select_resource(resource_states[activity], earliest_start, rng)
    start_at = max(earliest_start, resource_state.available_at)
    complete_at = start_at + duration
    resource_state.available_at = complete_at
    resource_state.workload_seconds += duration.total_seconds()
    instance_id = f"{case_id}_{_stable_activity_id(activity)}_{occurrence_counts[activity]:03d}"
    events = _events_for_instance(
        activity=activity,
        version_id=version_id,
        instance_id=instance_id,
        resource=resource_state.resource_id,
        start_at=start_at,
        complete_at=complete_at,
        assign_enabled=config.lifecycle.assign_enabled,
    )
    return EnrichedActivityInstance(
        activity=activity,
        occurrence_index=occurrence_counts[activity],
        instance_id=instance_id,
        resource=resource_state.resource_id,
        start_at=start_at,
        complete_at=complete_at,
        events=events,
    )


def _events_for_instance(
    *,
    activity: str,
    version_id: str,
    instance_id: str,
    resource: str,
    start_at: datetime,
    complete_at: datetime,
    assign_enabled: bool,
) -> tuple[EnrichedEvent, ...]:
    events = []
    if assign_enabled:
        events.append(
            EnrichedEvent(
                activity=activity,
                transition="assign",
                timestamp=start_at,
                resource=resource,
                instance_id=instance_id,
                version_id=version_id,
            )
        )
    events.append(
        EnrichedEvent(
            activity=activity,
            transition="start",
            timestamp=start_at,
            resource=resource,
            instance_id=instance_id,
            version_id=version_id,
        )
    )
    events.append(
        EnrichedEvent(
            activity=activity,
            transition="complete",
            timestamp=complete_at,
            resource=resource,
            instance_id=instance_id,
            version_id=version_id,
        )
    )
    return tuple(events)


def _select_resource(resources: list[_ResourceState], earliest_start: datetime, rng: Random) -> _ResourceState:
    available = [resource for resource in resources if resource.available_at <= earliest_start]
    candidates = available if available else resources
    minimum_workload = min(resource.workload_seconds for resource in candidates)
    lowest_workload = [resource for resource in candidates if resource.workload_seconds == minimum_workload]
    return rng.choice(sorted(lowest_workload, key=lambda item: item.resource_id))


def _build_resource_pools(trees: dict[str, TreeNode], pool_size: int) -> dict[str, tuple[str, ...]]:
    labels = sorted({label for tree in trees.values() for label in _visible_labels(tree)})
    return {
        label: tuple(f"resource_{_stable_activity_id(label)}_{index:03d}" for index in range(1, pool_size + 1))
        for label in labels
    }


def _validate_trace(labels: tuple[str, ...], root: TreeNode, version_id: str) -> None:
    allowed = set(_visible_labels(root))
    if not labels or any(label not in allowed for label in labels):
        raise ArtifactError(f"trace cannot be replayed against {version_id}")
    if root.label is not None:
        expected = (root.label,)
        if labels != expected:
            raise ArtifactError(f"trace cannot be replayed against {version_id}")
        return
    if root.operator == "->" and tuple(_visible_labels(root)) != labels:
        raise ArtifactError(f"trace cannot be replayed against {version_id}")
    if root.operator in {"X", "+"} and Counter(_visible_labels(root)) != Counter(labels):
        if root.operator == "X" and any(tuple(_visible_labels(child)) == labels for child in root.children):
            return
        raise ArtifactError(f"trace cannot be replayed against {version_id}")


def _validate_trace_labels_known(labels: tuple[str, ...], root: TreeNode, version_id: str) -> None:
    allowed = set(_visible_labels(root))
    if not labels or any(label not in allowed for label in labels):
        raise ArtifactError(f"trace cannot be replayed against {version_id}")


def _carryover_summary(
    traces: list[EnrichedTrace],
    version_activation_times: dict[str, datetime],
) -> dict[str, int]:
    ordered_versions = list(version_activation_times)
    summary: Counter[str] = Counter()
    for trace in traces:
        start_index = ordered_versions.index(trace.version_id)
        completion_index = start_index
        for index, version_id in enumerate(ordered_versions[start_index + 1 :], start=start_index + 1):
            if trace.complete_at >= version_activation_times[version_id]:
                completion_index = index
        delta = completion_index - start_index
        summary["same_version" if delta == 0 else f"plus_{delta}"] += 1
    return dict(summary)


def _version_id(trace: AnnotatedTrace) -> str:
    version_id = trace.attributes.get("concept:version")
    if not version_id:
        raise ArtifactError("annotated trace missing concept:version")
    return version_id


def _activity_labels(trace: AnnotatedTrace) -> tuple[str, ...]:
    labels = []
    for event in trace.events:
        activity = event.attributes.get("concept:name")
        if not activity:
            raise ArtifactError("annotated event missing concept:name")
        labels.append(activity)
    return tuple(labels)


def _stable_activity_id(label: str) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in label.lower()).strip("_")
    normalized = normalized or "activity"
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]
    return normalized if normalized.isascii() else digest
