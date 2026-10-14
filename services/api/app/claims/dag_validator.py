"""DAG Cycle Detection & Dependency Validator for Mathematical Claims.

Validates that mathematical derivations form a Directed Acyclic Graph (DAG)
without circular reasoning (ngụy biện vòng quanh - begging the question).
"""

from typing import Any, Union
from app.schemas.agent_contracts import ClaimItem


def _build_adj_list(
    claims: Union[list[ClaimItem], dict[str, list[str]], list[dict[str, Any]]]
) -> dict[str, list[str]]:
    """Builds adjacency list: node -> list of nodes it depends on."""
    adj: dict[str, list[str]] = {}

    if isinstance(claims, dict):
        return {str(k): [str(d) for d in v] for k, v in claims.items()}

    for item in claims:
        if isinstance(item, ClaimItem):
            label = item.label
            deps = list(item.depends_on)
        elif isinstance(item, dict):
            label = str(item.get("label", ""))
            deps = [str(d) for d in item.get("depends_on", [])]
        else:
            continue
        adj[label] = deps

    return adj


def validate_dependencies_exist(
    claims: Union[list[ClaimItem], dict[str, list[str]], list[dict[str, Any]]]
) -> list[str]:
    """Checks whether any claim depends on an undefined claim label.

    Returns a list of error messages for missing dependencies.
    """
    adj = _build_adj_list(claims)
    existing_labels = set(adj.keys())
    errors = []

    for label, deps in adj.items():
        for dep in deps:
            if dep not in existing_labels:
                errors.append(f"Mệnh đề '{label}' phụ thuộc vào '{dep}' nhưng '{dep}' không tồn tại trong danh sách.")

    return errors


def validate_claim_dag(
    claims: Union[list[ClaimItem], dict[str, list[str]], list[dict[str, Any]]]
) -> tuple[bool, list[str] | None]:
    """Performs DAG cycle detection using 3-color DFS (WHITE=0, GRAY=1, BLACK=2).

    Returns:
        tuple (is_valid, cycle_path):
        - is_valid: True if no cycle exists, False if circular dependency detected.
        - cycle_path: List of claim labels representing the cycle loop (e.g. ['C1', 'C2', 'C1']), or None.
    """
    adj = _build_adj_list(claims)

    WHITE = 0
    GRAY = 1
    BLACK = 2

    color: dict[str, int] = {node: WHITE for node in adj}
    parent: dict[str, str | None] = {node: None for node in adj}
    cycle_found: list[str] | None = None

    def dfs(u: str) -> bool:
        nonlocal cycle_found
        color[u] = GRAY

        for v in adj.get(u, []):
            if v not in color:
                # Target not in node set; will be flagged by validate_dependencies_exist
                continue

            if color[v] == GRAY:
                # Cycle found! Reconstruct cycle path from u back to v
                if u == v:
                    cycle_found = [u, u]
                    return True
                path = [v, u]
                curr = parent[u]
                while curr is not None and curr != v:
                    path.append(curr)
                    curr = parent[curr]
                path.append(v)
                path.reverse()
                cycle_found = path
                return True

            if color[v] == WHITE:
                parent[v] = u
                if dfs(v):
                    return True

        color[u] = BLACK
        return False

    for node in list(adj.keys()):
        if color[node] == WHITE:
            if dfs(node):
                return False, cycle_found

    return True, None


def topological_sort_claims(
    claims: Union[list[ClaimItem], dict[str, list[str]], list[dict[str, Any]]]
) -> list[str]:
    """Returns claims sorted topologically (axioms/facts first, deductions last).

    Raises ValueError if a cycle is detected.
    """
    is_valid, cycle = validate_claim_dag(claims)
    if not is_valid:
        cycle_str = " -> ".join(cycle) if cycle else "unknown"
        raise ValueError(f"Phát hiện suy luận vòng quanh (Circular Dependency) trong các mệnh đề: {cycle_str}")

    adj = _build_adj_list(claims)
    visited: set[str] = set()
    order: list[str] = []

    def dfs_order(node: str) -> None:
        visited.add(node)
        for dep in adj.get(node, []):
            if dep in adj and dep not in visited:
                dfs_order(dep)
        order.append(node)

    for node in adj:
        if node not in visited:
            dfs_order(node)

    return order


from dataclasses import dataclass, field


@dataclass
class DAGValidationResult:
    is_valid: bool
    missing_references: list[tuple[str, str]] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)


def validate_claims_dag(claims: list[Any]) -> DAGValidationResult:
    claim_map = {}
    for c in claims:
        cid = getattr(c, "claim_id", getattr(c, "label", getattr(c, "id", str(c))))
        claim_map[cid] = c

    missing_refs: list[tuple[str, str]] = []
    for claim in claims:
        cid = getattr(claim, "claim_id", getattr(claim, "label", getattr(claim, "id", str(claim))))
        deps = getattr(claim, "depends_on", [])
        for dep_id in deps:
            if dep_id not in claim_map:
                missing_refs.append((cid, dep_id))

    state: dict[str, int] = {c_id: 0 for c_id in claim_map}
    path: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node_id: str) -> None:
        state[node_id] = 1
        path.append(node_id)
        claim_obj = claim_map[node_id]
        deps = getattr(claim_obj, "depends_on", [])
        for dep_id in deps:
            if dep_id not in claim_map:
                continue
            if state[dep_id] == 1:
                cycle_start_idx = path.index(dep_id)
                cycles.append(path[cycle_start_idx:] + [dep_id])
            elif state[dep_id] == 0:
                dfs(dep_id)
        path.pop()
        state[node_id] = 2

    for c_id in claim_map:
        if state[c_id] == 0:
            dfs(c_id)

    return DAGValidationResult(
        is_valid=(len(missing_refs) == 0 and len(cycles) == 0),
        missing_references=missing_refs,
        cycles=cycles,
    )
