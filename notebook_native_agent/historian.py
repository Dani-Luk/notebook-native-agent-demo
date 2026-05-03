from __future__ import annotations

from typing import Any, Dict, Optional

from .registry import get_state, utc_ts
from .router import classify_cell_kind
from .utils import (
    count_matplotlib_figures,
    diff_snapshots,
    namespace_snapshot,
    normalize_code,
    public_namespace,
    minimal_symbol_metadata,
)


def _get_transformed_text(ip, info) -> str:
    raw = getattr(info, "raw_cell", "") or ""
    transformed = getattr(info, "transformed_cell", None)
    if transformed:
        return transformed
    try:
        return ip.transform_cell(raw)
    except Exception:
        return raw


def _proposal_match(raw_text: str) -> Optional[Dict[str, Any]]:
    state = get_state()
    norm = normalize_code(raw_text)
    if not norm:
        return None
    for proposal in reversed(state.pending_proposals):
        if proposal.get("status") != "pending":
            continue
        if proposal.get("normalized_code") == norm:
            return proposal
    return None


def _update_symbol_registry(
    diff: Dict[str, Any],
    user_ns: Dict[str, Any],
    linked_exec_id: Optional[int],
    proposal_match: Optional[Dict[str, Any]],
) -> None:
    state = get_state()
    if linked_exec_id is not None:
        provenance = "agent_auto_executed"
    elif proposal_match is not None:
        provenance = "agent_proposed_then_user_executed"
    else:
        provenance = "user_created"

    for item in diff["created"] + diff["modified"]:
        inferred_provenance = provenance
        if item["type"] == "module" and proposal_match is None and linked_exec_id is None:
            inferred_provenance = "user_imported"

        entry = {
            "type": item.get("type", "unknown"),
            "repr": item.get("repr", ""),
            "provenance": inferred_provenance,
            "last_seen_cell_id": state.cell_counter,
            "deleted": False,
        }

        value = user_ns.get(item["name"])
        if value is not None:
            entry.update(minimal_symbol_metadata(value))

        state.symbol_registry[item["name"]] = entry

    for item in diff["deleted"]:
        meta = state.symbol_registry.setdefault(item["name"], {})
        meta.update({"deleted": True, "last_seen_cell_id": state.cell_counter})

def _is_internal_notebook_cell(raw_text: str) -> bool:
    """
    Detect notebook/frontend-generated helper cells that should not be recorded.

    VS Code, Jupyter frontends, debuggers, dataframe viewers, and autocomplete
    tools may execute hidden helper cells in the kernel. These are not user code
    and should not pollute cell_history or symbol provenance.
    """
    text = raw_text or ""

    internal_markers = [
        # VS Code / Jupyter background completion
        "__jupyter_exec_background__",
        "application/vnd.vscode.bg.execution",
        "get_ipython().kernel.do_complete",

        # VS Code / debugger/data viewer helpers
        "DW_GET_DF_VARS",
        "DW_LOCALS",
        "DW_GLOBALS",
        "VSCODE",
        "vscode",
        "debugpy",
        "pydevd",
    ]

    return any(marker in text for marker in internal_markers)

def build_pre_run_hook(ip):
    def _pre_run(info):
        state = get_state()
        raw_text = getattr(info, "raw_cell", "") or ""

        if _is_internal_notebook_cell(raw_text):
            state.current_cell = None
            return

        user_ns = public_namespace(ip.user_ns)
        transformed_text = _get_transformed_text(ip, info)
        state.current_cell = {
            "cell_id": state.next_cell_id(),
            "raw_text": raw_text,
            "transformed_text": transformed_text,
            "cell_kind": classify_cell_kind(raw_text, transformed_text),
            "before_snapshot": namespace_snapshot(user_ns, repr_limit=state.config.max_repr_chars),
            "before_figures": count_matplotlib_figures(ip.user_ns),
            "started_at": utc_ts(),
            "linked_exec_id": None,
        }

    return _pre_run

def build_post_run_hook(ip):
    def _post_run(result):
        state = get_state()
        cell = state.current_cell
        if not cell:
            return

        error_obj = getattr(result, "error_in_exec", None) or getattr(result, "error_before_exec", None)
        after_snapshot = namespace_snapshot(public_namespace(ip.user_ns), repr_limit=state.config.max_repr_chars)
        diff = diff_snapshots(cell["before_snapshot"], after_snapshot)
        after_figures = count_matplotlib_figures(ip.user_ns)
        proposal_match = None
        if cell.get("cell_kind") == "python":
            proposal_match = _proposal_match(cell.get("raw_text", ""))
            if proposal_match is not None:
                proposal_match["status"] = "accepted"

        _update_symbol_registry(
            diff,
            public_namespace(ip.user_ns),
            cell.get("linked_exec_id"),
            proposal_match,
        )

        cell_record = {
            "cell_id": cell["cell_id"],
            "raw_text": cell["raw_text"],
            "transformed_text": cell["transformed_text"],
            "cell_kind": cell["cell_kind"],
            "status": "error" if error_obj else "executed",
            "linked_exec_id": cell.get("linked_exec_id"),
            "symbols_created": [item["name"] for item in diff["created"]],
            "symbols_modified": [item["name"] for item in diff["modified"]],
            "symbols_deleted": [item["name"] for item in diff["deleted"]],
            "started_at": cell["started_at"],
            "finished_at": utc_ts(),
        }
        state.cell_history.append(cell_record)

        figure_delta = max(0, after_figures - cell.get("before_figures", 0))
        for _ in range(figure_delta):
            state.artifact_registry.append(
                {
                    "kind": "matplotlib_figure",
                    "cell_id": cell["cell_id"],
                    "linked_exec_id": cell.get("linked_exec_id"),
                    "created_at": utc_ts(),
                }
            )

        if cell.get("linked_exec_id") is not None:
            for record in reversed(state.exec_history):
                if record["exec_id"] == cell["linked_exec_id"]:
                    record["status"] = cell_record["status"]
                    record["finished_at"] = utc_ts()
                    record["cell_id"] = cell["cell_id"]
                    record["artifact_count"] = figure_delta
                    break

        raw_text = cell.get("raw_text", "")
        should_review_python_error = bool(
            error_obj
            and cell.get("cell_kind") == "python"
            and cell.get("linked_exec_id") is None
            and not getattr(state, "paused", False)
            and getattr(state.config, "assist_on_python_error", True)
        )
        state.current_cell = None

        if should_review_python_error:
            try:
                from .handler import handle_failed_python_cell_review  # noqa: WPS433

                handle_failed_python_cell_review(
                    raw_code=raw_text,
                    error_obj=error_obj,
                    user_ns=public_namespace(ip.user_ns),
                )
            except Exception:
                pass

    return _post_run
