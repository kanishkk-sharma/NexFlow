"""Graph validation and the streaming workflow engine."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any, AsyncIterator

from .config import get_settings
from .executors import EXECUTORS, ExecutionContext, NodeError, stringify

log = logging.getLogger("nexflow.engine")


def _edge_key(edge: dict, field: str) -> str | None:
    value = edge.get(field)
    return None if value is None else str(value)


def topological_order(nodes: list[dict], edges: list[dict]) -> list[str] | None:
    """Kahn's algorithm. Returns None when the graph has a cycle."""
    ids = [str(n["id"]) for n in nodes]
    indegree = {nid: 0 for nid in ids}
    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        source, target = _edge_key(edge, "source"), _edge_key(edge, "target")
        if source in indegree and target in indegree:
            children[source].append(target)
            indegree[target] += 1
    queue = deque(nid for nid in ids if indegree[nid] == 0)
    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return order if len(order) == len(ids) else None


def analyze_graph(nodes: list[dict], edges: list[dict]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    ids = [str(n["id"]) for n in nodes]
    id_set = set(ids)

    if len(id_set) != len(ids):
        errors.append("Node ids must be unique")
    for node in nodes:
        if node.get("type") not in EXECUTORS:
            errors.append(f"Node '{node['id']}' has unknown type '{node.get('type')}'")
    for edge in edges:
        source, target = _edge_key(edge, "source"), _edge_key(edge, "target")
        if source not in id_set or target not in id_set:
            errors.append(f"Connection {source} -> {target} points to a missing node")
        elif source == target:
            errors.append(f"Node '{source}' is connected to itself")

    order = topological_order(nodes, edges) if len(id_set) == len(ids) else None
    is_dag = order is not None
    if order is None and len(id_set) == len(ids):
        errors.append("Workflow contains a cycle")

    if nodes:
        if not any(n.get("type") == "customOutput" for n in nodes):
            warnings.append("Workflow has no Output node, so results will only be visible per node")
        connected = {_edge_key(e, "source") for e in edges} | {_edge_key(e, "target") for e in edges}
        if len(nodes) > 1:
            for nid in ids:
                if nid not in connected:
                    warnings.append(f"Node '{nid}' is not connected to anything")
    else:
        warnings.append("Workflow is empty")

    return {
        "num_nodes": len(nodes),
        "num_edges": len(edges),
        "is_dag": is_dag,
        "errors": errors,
        "warnings": warnings,
        "execution_order": order if (order and not errors) else [],
    }


def to_jsonable(value: Any) -> Any:
    """Make a value strictly JSON-safe and cap its size."""
    limit = get_settings().max_output_chars
    text = json.dumps(value, default=str, ensure_ascii=False)
    if len(text) > limit:
        return {"truncated": True, "original_chars": len(text), "preview": text[:limit]}
    return json.loads(text, parse_constant=lambda _c: None)


def _edge_payload(source_type: str, output: Any) -> Any:
    if source_type == "condition" and isinstance(output, dict):
        return output.get("value")
    return output


async def _call_executor(ntype: str, ctx: ExecutionContext, data: dict, inputs: dict) -> Any:
    executor = EXECUTORS[ntype]
    timeout = get_settings().node_timeout_s
    if asyncio.iscoroutinefunction(executor):
        return await asyncio.wait_for(executor(ctx, data, inputs), timeout=timeout)
    return await asyncio.wait_for(asyncio.to_thread(executor, ctx, data, inputs), timeout=timeout)


async def run_workflow(nodes: list[dict], edges: list[dict], user_id: str) -> AsyncIterator[dict[str, Any]]:
    """Run a workflow, yielding {"event": name, "data": {...}} as nodes progress."""
    analysis = analyze_graph(nodes, edges)
    if analysis["errors"]:
        yield {"event": "error", "data": {"detail": "; ".join(analysis["errors"])}}
        return
    if not nodes:
        yield {"event": "error", "data": {"detail": "Workflow is empty"}}
        return

    order: list[str] = analysis["execution_order"]
    lookup = {str(n["id"]): n for n in nodes}
    incoming: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        incoming[str(edge["target"])].append(edge)

    started = time.perf_counter()
    yield {"event": "start", "data": {"execution_order": order, "total": len(order)}}

    ctx = ExecutionContext(user_id)
    outputs: dict[str, Any] = {}
    active_handles: dict[str, set[str]] = {}
    skipped: set[str] = set()
    completed = 0
    named_outputs: dict[str, Any] = {}

    try:
        for position, nid in enumerate(order, start=1):
            node = lookup[nid]
            ntype = node["type"]
            data = node.get("data") or {}

            inputs: dict[str, Any] = {}
            live_edges = 0
            for edge in incoming[nid]:
                source = str(edge["source"])
                if source in skipped or source not in outputs:
                    continue
                allowed = active_handles.get(source)
                if allowed is not None and _edge_key(edge, "sourceHandle") not in allowed:
                    continue
                live_edges += 1
                inputs[_edge_key(edge, "targetHandle") or "value"] = _edge_payload(
                    lookup[source]["type"], outputs[source]
                )

            if incoming[nid] and live_edges == 0:
                skipped.add(nid)
                yield {"event": "node_skipped", "data": {
                    "node_id": nid, "node_type": ntype, "position": position, "status": "skipped",
                    "reason": "No active input (upstream branch was not taken)",
                }}
                continue

            yield {"event": "node_start", "data": {"node_id": nid, "node_type": ntype, "position": position}}
            node_started = time.perf_counter()
            try:
                raw_output = await _call_executor(ntype, ctx, data, inputs)
                output = to_jsonable(raw_output)
            except asyncio.TimeoutError:
                message = f"Node timed out after {get_settings().node_timeout_s}s"
                yield _node_failure(nid, ntype, position, message, node_started)
                yield _done("failed", completed, started, named_outputs, f"Node '{nid}' failed: {message}")
                return
            except NodeError as exc:
                yield _node_failure(nid, ntype, position, str(exc), node_started)
                yield _done("failed", completed, started, named_outputs, f"Node '{nid}' failed: {exc}")
                return
            except Exception as exc:  # noqa: BLE001 - unexpected bug; never crash the stream
                log.exception("Unexpected failure in node %s (%s)", nid, ntype)
                message = f"Unexpected error: {type(exc).__name__}"
                yield _node_failure(nid, ntype, position, message, node_started)
                yield _done("failed", completed, started, named_outputs, f"Node '{nid}' failed: {message}")
                return

            outputs[nid] = output
            completed += 1
            if ntype == "condition" and isinstance(output, dict):
                active_handles[nid] = {output.get("branch", "false")}
            if ntype == "customOutput":
                label = stringify(data.get("outputName")).strip() or nid
                named_outputs[label if label not in named_outputs else f"{label} ({nid})"] = output

            yield {"event": "node_complete", "data": {
                "node_id": nid, "node_type": ntype, "position": position, "status": "completed",
                "inputs": to_jsonable(inputs), "output": output,
                "duration_ms": round((time.perf_counter() - node_started) * 1000),
            }}

        yield _done("success", completed, started, named_outputs, None, skipped=len(skipped))
    finally:
        ctx.close()


def _node_failure(nid: str, ntype: str, position: int, message: str, node_started: float) -> dict[str, Any]:
    return {"event": "node_error", "data": {
        "node_id": nid, "node_type": ntype, "position": position, "status": "failed",
        "error": message, "duration_ms": round((time.perf_counter() - node_started) * 1000),
    }}


def _done(status: str, completed: int, started: float, outputs: dict, error: str | None, skipped: int = 0) -> dict[str, Any]:
    return {"event": "done", "data": {
        "status": status,
        "message": "Workflow executed successfully." if status == "success" else error,
        "error": error,
        "nodes_executed": completed,
        "nodes_skipped": skipped,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "outputs": outputs,
    }}
