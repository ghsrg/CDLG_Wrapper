from __future__ import annotations

import csv
import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from pm4py.objects.bpmn.exporter import exporter as bpmn_exporter
from pm4py.objects.conversion.process_tree import converter as process_tree_converter
from pm4py.objects.process_tree.exporter import exporter as ptml_exporter
from pm4py.objects.process_tree.utils.generic import parse as parse_process_tree

from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.errors import ArtifactError


BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
ET.register_namespace("bpmn", BPMN_NS)


@dataclass(frozen=True)
class StructureArtifact:
    version_id: str
    ptml_path: Path
    bpmn_path: Path
    id_mapping: dict[str, str]


@dataclass(frozen=True)
class StructureExportResult:
    artifacts: tuple[StructureArtifact, ...]
    catalog_path: Path


@dataclass(frozen=True)
class TreeNode:
    operator: str | None
    label: str | None
    children: tuple["TreeNode", ...] = ()


def export_structures(
    *,
    snapshots: tuple[ProcessTreeSnapshot, ...],
    output_root: Path,
) -> StructureExportResult:
    ptml_dir = output_root / "models/ptml"
    bpmn_dir = output_root / "models/bpmn"
    ptml_dir.mkdir(parents=True, exist_ok=True)
    bpmn_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[StructureArtifact] = []
    for snapshot in snapshots:
        root_node = _parse_tree_string(snapshot.process_tree)
        labels = _visible_labels(root_node)
        if len(labels) != len(set(labels)):
            raise ArtifactError(f"duplicate visible activity label in {snapshot.version_id}")

        ptml_path = ptml_dir / f"{snapshot.version_id}.ptml"
        bpmn_path = bpmn_dir / f"{snapshot.version_id}.bpmn"
        _export_ptml(snapshot.process_tree, ptml_path)
        id_mapping = _export_bpmn(snapshot.process_tree, root_node, bpmn_path)
        artifacts.append(
            StructureArtifact(
                version_id=snapshot.version_id,
                ptml_path=ptml_path,
                bpmn_path=bpmn_path,
                id_mapping=id_mapping,
            )
        )

    catalog_path = output_root / "models/process_definitions.csv"
    _write_catalog(catalog_path, artifacts)
    return StructureExportResult(artifacts=tuple(artifacts), catalog_path=catalog_path)


def _export_ptml(process_tree: str, path: Path) -> None:
    try:
        tree = parse_process_tree(_pm4py_process_tree(process_tree))
        ptml_exporter.apply(tree, str(path))
    except Exception as error:
        raise ArtifactError(f"process_tree cannot be exported to PTML: {process_tree}") from error


def _export_bpmn(process_tree: str, root_node: TreeNode, path: Path) -> dict[str, str]:
    try:
        tree = parse_process_tree(_pm4py_process_tree(process_tree))
        bpmn_graph = process_tree_converter.apply(tree, variant=process_tree_converter.Variants.TO_BPMN)
        bpmn_exporter.apply(bpmn_graph, str(path))
    except Exception as error:
        raise ArtifactError(f"process_tree cannot be converted to BPMN: {process_tree}") from error
    return _normalize_bpmn_xml(path, root_node)


def _write_catalog(path: Path, artifacts: list[StructureArtifact]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "proc_def_id",
                "proc_def_key",
                "version",
                "tenant_id",
                "deployment_id",
                "bpmn_path",
            ],
        )
        writer.writeheader()
        for artifact in artifacts:
            writer.writerow(
                {
                    "proc_def_id": f"cdlg_{artifact.version_id}",
                    "proc_def_key": "cdlg_dataset",
                    "version": artifact.version_id,
                    "tenant_id": "",
                    "deployment_id": f"cdlg_deployment_{artifact.version_id}",
                    "bpmn_path": f"models/bpmn/{artifact.version_id}.bpmn",
                }
            )


def _normalize_bpmn_xml(path: Path, root_node: TreeNode) -> dict[str, str]:
    xml_tree = ET.parse(path)
    definitions = xml_tree.getroot()
    _remove_diagram_elements(definitions)

    process = definitions.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        raise ArtifactError("BPMN export missing process")

    definitions.attrib["id"] = "definitions_cdlg"
    process.attrib["id"] = "process_cdlg"

    id_mapping = _normalized_node_id_map(process, root_node)
    for element in process.findall(".//*[@id]"):
        old_id = element.attrib["id"]
        if old_id in id_mapping:
            element.attrib["id"] = id_mapping[old_id]

    for flow in process.findall(f".//{{{BPMN_NS}}}sequenceFlow"):
        flow.attrib["sourceRef"] = id_mapping.get(flow.attrib["sourceRef"], flow.attrib["sourceRef"])
        flow.attrib["targetRef"] = id_mapping.get(flow.attrib["targetRef"], flow.attrib["targetRef"])

    _normalize_flow_ids(process)
    _sort_process_children(process)
    _validate_bpmn(process)
    xml_tree.write(path, encoding="utf-8", xml_declaration=True)
    return _public_id_mapping(process)


def _remove_diagram_elements(definitions: ET.Element) -> None:
    for child in list(definitions):
        if child.tag.startswith(f"{{{BPMNDI_NS}}}"):
            definitions.remove(child)


def _normalized_node_id_map(process: ET.Element, root_node: TreeNode) -> dict[str, str]:
    assignments: list[tuple[str, str]] = []
    label_order = {label: index for index, label in enumerate(_visible_labels(root_node))}
    for task in sorted(
        process.findall(f".//{{{BPMN_NS}}}task"),
        key=lambda item: (label_order.get(item.attrib["name"], len(label_order)), item.attrib["name"]),
    ):
        assignments.append((task.attrib["id"], _task_id(task.attrib["name"])))

    for index, start_event in enumerate(process.findall(f".//{{{BPMN_NS}}}startEvent"), start=1):
        assignments.append((start_event.attrib["id"], "start_event" if index == 1 else f"start_event_{index}"))
    for index, end_event in enumerate(process.findall(f".//{{{BPMN_NS}}}endEvent"), start=1):
        assignments.append((end_event.attrib["id"], "end_event" if index == 1 else f"end_event_{index}"))

    gateway_signatures = _gateway_signatures(root_node)
    used_gateway_counts: dict[tuple[str, str], int] = {}
    for gateway in _gateway_elements(process):
        kind = _gateway_kind_from_tag(gateway.tag)
        role = _gateway_role(process, gateway.attrib["id"])
        occurrence = used_gateway_counts.get((kind, role), 0)
        signatures = gateway_signatures.get((kind, role), ())
        signature = signatures[occurrence] if occurrence < len(signatures) else f"{kind}:{role}:{occurrence}"
        used_gateway_counts[(kind, role)] = occurrence + 1
        assignments.append((gateway.attrib["id"], _gateway_id(kind, role, signature)))

    return _assign_deterministic_collision_suffixes(assignments)


def _assign_deterministic_collision_suffixes(assignments: list[tuple[str, str]]) -> dict[str, str]:
    used_counts: dict[str, int] = {}
    id_mapping: dict[str, str] = {}
    for old_id, base_id in assignments:
        used_counts[base_id] = used_counts.get(base_id, 0) + 1
        occurrence = used_counts[base_id]
        id_mapping[old_id] = base_id if occurrence == 1 else f"{base_id}_{occurrence:03d}"
    return id_mapping


def _normalize_flow_ids(process: ET.Element) -> None:
    flows = sorted(
        process.findall(f".//{{{BPMN_NS}}}sequenceFlow"),
        key=lambda flow: (flow.attrib["sourceRef"], flow.attrib["targetRef"]),
    )
    for index, flow in enumerate(flows, start=1):
        flow.attrib["id"] = f"flow_{index:03d}"


def _sort_process_children(process: ET.Element) -> None:
    children = list(process)
    process[:] = sorted(children, key=_process_child_sort_key)


def _process_child_sort_key(element: ET.Element) -> tuple[int, str]:
    local_name = _local_name(element.tag)
    if local_name == "startEvent":
        return (0, element.attrib.get("id", ""))
    if local_name == "task":
        return (1, element.attrib.get("id", ""))
    if local_name.endswith("Gateway"):
        role_order = 0 if "_split_" in element.attrib.get("id", "") else 1
        return (2, f"{role_order}:{element.attrib.get('id', '')}")
    if local_name == "endEvent":
        return (3, element.attrib.get("id", ""))
    if local_name == "sequenceFlow":
        return (4, element.attrib.get("id", ""))
    return (5, element.attrib.get("id", ""))


def _public_id_mapping(process: ET.Element) -> dict[str, str]:
    mapping = {}
    for task in process.findall(f".//{{{BPMN_NS}}}task"):
        mapping[task.attrib["name"]] = task.attrib["id"]
    for gateway in _gateway_elements(process):
        mapping[gateway.attrib["id"]] = gateway.attrib["id"]
    return mapping


def _gateway_kind(operator: str | None) -> str:
    if operator == "+":
        return "parallel"
    if operator == "X":
        return "exclusive"
    if operator == "*":
        return "loop"
    raise ArtifactError(f"unsupported BPMN operator: {operator}")


def _gateway_id(gateway_kind: str, role: str, signature: str) -> str:
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:8]
    return f"gateway_{gateway_kind}_{role}_{digest}"


def _gateway_kind_from_tag(tag: str) -> str:
    local_name = _local_name(tag)
    if local_name == "parallelGateway":
        return "parallel"
    if local_name == "inclusiveGateway":
        return "inclusive"
    return "exclusive"


def _gateway_role(process: ET.Element, gateway_id: str) -> str:
    incoming = 0
    outgoing = 0
    for flow in process.findall(f".//{{{BPMN_NS}}}sequenceFlow"):
        if flow.attrib["targetRef"] == gateway_id:
            incoming += 1
        if flow.attrib["sourceRef"] == gateway_id:
            outgoing += 1
    return "split" if outgoing >= incoming else "join"


def _gateway_signatures(root_node: TreeNode) -> dict[tuple[str, str], tuple[str, ...]]:
    signatures: dict[tuple[str, str], list[str]] = {}
    for node in _operator_nodes(root_node):
        if node.operator in {"->", "tau"}:
            continue
        kind = _gateway_kind(node.operator)
        signature = _canonical_signature(node)
        signatures.setdefault((kind, "split"), []).append(signature)
        signatures.setdefault((kind, "join"), []).append(signature)
    return {key: tuple(value) for key, value in signatures.items()}


def _operator_nodes(node: TreeNode) -> list[TreeNode]:
    if node.operator == "tau":
        return []
    nodes = [] if node.label is not None else [node]
    for child in node.children:
        nodes.extend(_operator_nodes(child))
    return nodes


def _gateway_elements(process: ET.Element) -> list[ET.Element]:
    return [
        element
        for element in process.findall(".//*[@id]")
        if _local_name(element.tag).endswith("Gateway")
    ]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _canonical_signature(node: TreeNode) -> str:
    if node.operator == "tau":
        return "tau"
    if node.label is not None:
        return repr(node.label)
    child_signatures = ",".join(_canonical_signature(child) for child in node.children)
    return f"{node.operator}({child_signatures})"


def _validate_bpmn(process: ET.Element) -> None:
    elements_with_ids = process.findall(".//*[@id]")
    ids = [element.attrib["id"] for element in elements_with_ids]
    if len(ids) != len(set(ids)):
        raise ArtifactError("BPMN IDs are not unique")
    id_set = set(ids)
    for flow in process.findall(f".//{{{BPMN_NS}}}sequenceFlow"):
        if flow.attrib["sourceRef"] not in id_set or flow.attrib["targetRef"] not in id_set:
            raise ArtifactError("BPMN sequence flow references missing endpoint")


def _task_id(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "activity"
    digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]
    return f"task_{normalized}_{digest}"


def _visible_labels(node: TreeNode) -> list[str]:
    if node.operator == "tau":
        return []
    if node.label is not None:
        return [node.label]
    labels: list[str] = []
    for child in node.children:
        labels.extend(_visible_labels(child))
    return labels


def _parse_tree_string(value: str) -> TreeNode:
    parser = _TreeParser(value)
    node = parser.parse_node()
    parser.require_end()
    return node


def _pm4py_process_tree(value: str) -> str:
    return value.replace("*tau*", "tau")


class _TreeParser:
    def __init__(self, value: str) -> None:
        self.value = value
        self.index = 0

    def parse_node(self) -> TreeNode:
        self._skip_ws()
        if self.value.startswith("*tau*", self.index):
            self.index += len("*tau*")
            return TreeNode(operator="tau", label=None)
        if self._peek() == "'":
            return TreeNode(operator=None, label=self._parse_label())
        operator = self._parse_operator()
        self._expect("(")
        children = [self.parse_node()]
        while True:
            self._skip_ws()
            if self._peek() == ")":
                self.index += 1
                break
            self._expect(",")
            children.append(self.parse_node())
        return TreeNode(operator=operator, label=None, children=tuple(children))

    def require_end(self) -> None:
        self._skip_ws()
        if self.index != len(self.value):
            raise ArtifactError(f"invalid process_tree trailing content: {self.value}")

    def _parse_label(self) -> str:
        self._expect("'")
        start = self.index
        while self.index < len(self.value) and self.value[self.index] != "'":
            self.index += 1
        if self.index >= len(self.value):
            raise ArtifactError(f"unterminated process_tree label: {self.value}")
        label = self.value[start:self.index]
        self.index += 1
        if not label:
            raise ArtifactError("empty visible activity label")
        return label

    def _parse_operator(self) -> str:
        for operator in ("->", "X", "+", "*"):
            if self.value.startswith(operator, self.index):
                self.index += len(operator)
                return operator
        raise ArtifactError(f"invalid process_tree operator: {self.value}")

    def _expect(self, token: str) -> None:
        self._skip_ws()
        if not self.value.startswith(token, self.index):
            raise ArtifactError(f"invalid process_tree syntax near: {self.value[self.index:]}")
        self.index += len(token)

    def _peek(self) -> str:
        self._skip_ws()
        if self.index >= len(self.value):
            return ""
        return self.value[self.index]

    def _skip_ws(self) -> None:
        while self.index < len(self.value) and self.value[self.index].isspace():
            self.index += 1
