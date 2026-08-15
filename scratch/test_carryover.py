from datetime import datetime, timezone
from random import Random
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig
from wrapper.enrichment import EnrichmentConfig, enrich_traces
from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.annotate_versions import AnnotatedTrace, AnnotatedEvent

# 12 activities in sequence with loop
acts = [f"act_{i}" for i in range(12)]
tree_str = f"->( {', '.join([repr(a) for a in acts])} )"
snapshots = tuple(ProcessTreeSnapshot(f'v{i}', tree_str) for i in range(1, 6))

def test_config(name, arrival_rate, duration_mu, duration_sigma, pool_size):
    traces = []
    idx = 0
    for v in range(1, 6):
        for _ in range(400):
            idx += 1
            # 12-20 events per trace
            events = tuple(AnnotatedEvent({'concept:name': act}) for act in acts)
            traces.append(AnnotatedTrace(idx, {'concept:version': f'v{v}'}, events))
            
    cfg = EnrichmentConfig(
        lifecycle=LifecycleConfig(assign_enabled=False),
        resources=ResourceConfig(pool_size=pool_size),
        temporal=TemporalConfig(
            arrival_rate=arrival_rate,
            duration_mu=duration_mu,
            duration_sigma=duration_sigma,
            epoch=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    res = enrich_traces(traces=tuple(traces), snapshots=snapshots, config=cfg, rng=Random(0))
    v1_traces = [t for t in res.traces if t.version_id == 'v1']
    v2_activation = res.version_activation_times['v2']
    v1_in_v1 = sum(1 for t in v1_traces if t.complete_at < v2_activation)
    v1_spill = len(v1_traces) - v1_in_v1
    
    print(f"[{name}] arr={arrival_rate}, mu={duration_mu}, sig={duration_sigma}, pool={pool_size}")
    print(f"    v1 spillover into v2+: {v1_spill}/400 ({v1_spill/400*100:.1f}%)")
    print(f"    Total summary: {res.carryover_summary}")

# Let's test target settings:
test_config("Setting A", arrival_rate=0.5, duration_mu=0.0, duration_sigma=0.5, pool_size=5)
test_config("Setting B", arrival_rate=0.5, duration_mu=-0.5, duration_sigma=0.5, pool_size=3)
test_config("Setting C", arrival_rate=0.8, duration_mu=-0.5, duration_sigma=0.5, pool_size=4)
test_config("Setting D", arrival_rate=1.0, duration_mu=-0.8, duration_sigma=0.5, pool_size=3)
test_config("Setting E", arrival_rate=1.0, duration_mu=-0.2, duration_sigma=0.8, pool_size=5)
