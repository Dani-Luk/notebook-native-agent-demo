from __future__ import annotations

from pprint import pprint
from typing import Any, Dict, Optional

from .registry import get_state


def agent_status(*, just_show: bool = True) -> Optional[Dict[str, Any]]:
    state = get_state()

    active_symbols = {
        name: meta
        for name, meta in state.symbol_registry.items()
        if not meta.get("deleted")
    }
    pending_proposals = [
        proposal
        for proposal in state.pending_proposals
        if proposal.get("status") == "pending"
    ]

    data = {
        "started": state.started,
        "paused": state.paused,
        "agent_name": state.config.name,
        "provider": state.config.provider,
        "auto_execute": state.config.auto_execute,
        "allow_fallback_codegen": state.config.allow_fallback_codegen,
        "use_model_classifier": state.config.use_model_classifier,
        "echo_context": state.config.echo_context,
        "brain_model": state.config.brain_model,
        "summarizer_model": state.config.summarizer_model,
        "interpreter_model": state.config.interpreter_model,
        "repair_model": state.config.repair_model,
        "counts": {
            "cells": len(state.cell_history),
            "execs": len(state.exec_history),
            "active_symbols": len(active_symbols),
            "artifacts": len(state.artifact_registry),
            "pending_proposals": len(pending_proposals),
        },
        "current_cell": (
            {
                "cell_id": state.current_cell.get("cell_id"),
                "cell_kind": state.current_cell.get("cell_kind"),
                "linked_exec_id": state.current_cell.get("linked_exec_id"),
            }
            if state.current_cell
            else None
        ),
    }

    if just_show:
        pprint(data, sort_dicts=False)
        return None
    return data


def agent_symbols(*, active_only: bool = True, just_show: bool = True) -> Optional[Dict[str, Dict[str, Any]]]:
    state = get_state()

    data: Dict[str, Dict[str, Any]] = {}
    for name, meta in state.symbol_registry.items():
        if active_only and meta.get("deleted"):
            continue

        data[name] = {
            "type": meta.get("type"),
            "symbol_kind": meta.get("kind"),
            "signature": meta.get("signature"),
            "docstring": meta.get("docstring"),
            "public_member_names": meta.get("public_member_names"),
            "public_callable_signatures": meta.get("public_callable_signatures"),
            "provenance": meta.get("provenance"),
            "last_seen_cell_id": meta.get("last_seen_cell_id"),
            "deleted": meta.get("deleted", False),
            "repr": meta.get("repr"),
        }

    if just_show:
        pprint(data, sort_dicts=False)
        return None
    return data