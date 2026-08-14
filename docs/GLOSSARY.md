# Glossary

| Term | Definition | Status | Canonical Source |
| --- | --- | --- | --- |
| `wrapper` | Benchmark-owned program that invokes CDLG and assembles validated output artifacts. | confirmed | [README](../README.md) |
| `external CDLG checkout` | Ignored local checkout of the pinned upstream CDLG repository used only as an external runtime. | confirmed | [AGENTS](../AGENTS.md) |
| `process version` | Ordered member of the evolutionary chain `v1` ... `vN`. | confirmed | [Design specification](wrapper-design.md) |
| `versioned XES` | Unified XES dataset whose traces and events carry explicit process-version metadata. | confirmed | [Design specification](wrapper-design.md) |
| `artifact contract` | Required output files, attributes, reports, and validation conditions for one dataset. | confirmed | [Design specification](wrapper-design.md) |
| `mapping rules` | Explicit rules and configuration describing how source/generated fields map to downstream XES/BPMN fields. | confirmed | User decision, [Design specification](wrapper-design.md) |
| `evidence bundle` | Configurations, raw output, command trace, logs, reports, environment metadata, and checksums associated with a run. | confirmed | [Design specification](wrapper-design.md) |
| `valid dataset` | Dataset that completed the full pipeline and passed mandatory validation. | confirmed | User decision, [Project principles](PRINCIPLES.md) |
| `failed run` | Run that cannot publish a valid dataset because generation, processing, export, evidence, or validation failed. | confirmed | [Design specification](wrapper-design.md) |
| `structural drift` | Change in process structure between process versions. | confirmed | [Design specification](wrapper-design.md) |
| `BPMN-first topology` | Policy that BPMN is the primary topology source, while XES-derived topology is fallback or QA evidence. | confirmed | [Design specification](wrapper-design.md) |
| `PTML audit artifact` | PTML representation retained as the canonical CDLG/process-tree structure artifact for audit. | confirmed | [Design specification](wrapper-design.md) |
