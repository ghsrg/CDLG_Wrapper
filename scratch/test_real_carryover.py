from datetime import datetime, timezone
from pathlib import Path
from random import Random
from wrapper.annotate_versions import annotate_versions
from wrapper.cdlg_metadata import parse_raw_metadata
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig, load_config
from wrapper.enrichment import EnrichmentConfig, enrich_traces

run_dir = Path("outputs/datasets/run-20260815T194257266530Z")
config = load_config(Path("configs/cdlg_experiment.yaml"))
version_ids = tuple(f"v{i}" for i in range(1, config.dataset.version_count + 1))
metadata = parse_raw_metadata(
    raw_xes_path=run_dir / "raw" / "cdlg_output.xes",
    drift_csv_path=run_dir / "raw" / "drift_info.csv",
    expected_version_ids=version_ids,
)
annotated = annotate_versions(
    raw_xes_path=run_dir / "raw" / "cdlg_output.xes",
    metadata=metadata,
    resolved_config=config,
)

def sim(pool_size, arr, mu, sig):
    cfg = EnrichmentConfig(
        lifecycle=LifecycleConfig(assign_enabled=False),
        resources=ResourceConfig(pool_size=pool_size),
        temporal=TemporalConfig(
            arrival_rate=arr,
            duration_mu=mu,
            duration_sigma=sig,
            epoch=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    )
    res = enrich_traces(traces=annotated.traces, snapshots=metadata.snapshots, config=cfg, rng=Random(0))
    v1_traces = [t for t in res.traces if t.version_id == "v1"]
    v2_activation = res.version_activation_times["v2"]
    v1_in_v1 = sum(1 for t in v1_traces if t.complete_at < v2_activation)
    v1_spill = len(v1_traces) - v1_in_v1
    print(f"pool={pool_size:2d}, arr={arr:4.2f}, mu={mu:4.1f}, sig={sig:3.1f} -> v1 spill: {v1_spill/400*100:5.1f}% ({v1_spill}/400) | total same: {res.carryover_summary.get('same_version', 0)}/2000 | summary: {res.carryover_summary}")

print("=== Fine-tuning for 10-20% carryover on actual dataset ===")
for pool in [5, 6, 8, 10]:
    for arr in [0.05, 0.08, 0.10, 0.12, 0.15]:
        for mu in [-0.5, 0.0]:
            sim(pool, arr, mu, 0.5)
