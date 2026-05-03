from __future__ import annotations

import json
from typing import List

from .registry import get_state
from .utils import call_model, classify_python_syntax, coerce_jsonish


CLASSIFIER_PROMPT = (
    "Classify the notebook cell. Return JSON with key 'kind' and value 'python' or 'agent_nl'."
)


def classify_cell(raw_text: str) -> str:
    state = get_state()
    if classify_python_syntax(raw_text):
        return "python"

    if not state.config.use_model_classifier:
        return "agent_nl"

    default = {"kind": "agent_nl"}
    response = call_model(
        None,
        CLASSIFIER_PROMPT,
        {"raw_text": raw_text},
        default=default,
        role_name="classifier",
        config=state.config,
    )
    result = coerce_jsonish(response, default)
    return result.get("kind", "agent_nl")


def classify_cell_kind(raw_text: str, transformed_text: str) -> str:
    transformed = (transformed_text or "").strip()
    if transformed.startswith("__auto_agent_handle__("):
        return "agent_nl"
    return classify_cell(raw_text)


def transform_cell(raw_text: str) -> str:
    kind = classify_cell(raw_text)
    if kind == "python":
        return raw_text
    return f"__auto_agent_handle__({json.dumps(raw_text)})"


def build_input_transformer():
    def _transform(lines: List[str]) -> List[str]:
        raw_text = "".join(lines)
        transformed = transform_cell(raw_text)
        if transformed == raw_text:
            return lines
        return [transformed + ("\n" if not transformed.endswith("\n") else "")]
    return _transform
