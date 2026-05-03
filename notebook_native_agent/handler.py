from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError
import textwrap

from .display import show_agent_panel, show_message
from .registry import get_state, utc_ts
from .safety import classify_execution
from .utils import (
    call_model,
    can_call_model,
    coerce_jsonish,
    explicit_no_run,
    explicit_run,
    normalize_code,
    public_namespace,
    score_overlap,
    short_repr,
)


class CodePlan(BaseModel):
    understood: str = Field(min_length=1)
    solution: str = Field(min_length=1)
    code: str = Field(min_length=1)
    should_auto_execute: bool = False


class ErrorReviewPlan(BaseModel):
    understood: str = Field(min_length=1)
    solution: str = Field(min_length=1)
    code: str = Field(min_length=1)


# BRAIN_PROMPT = (
#     "You are the brain of a notebook-native coding assistant. "
#     "Return ONLY valid JSON. "
#     "Schema:\n"
#     "{\n"
#     '  "understood": string,\n'
#     '  "solution": string,\n'
#     '  "code": string,\n'
#     '  "should_auto_execute": boolean\n'
#     "}\n"
#     "Rules:\n"
#     "- understood must be a short natural-language restatement of the request.\n"
#     "- solution must be a short explanation of the approach.\n"
#     "- code must be a Python code string.\n"
#     "- should_auto_execute must be true or false.\n"
#     "- Do not return markdown.\n"
#     "- Do not wrap JSON in triple backticks.\n"
#     "- Prefer reusing existing notebook symbols.\n"
#     "- Do not invent unavailable symbols.\n"
#     "Example:\n"
#     "{\n"
#     '  "understood": "Plot the monthly revenue trend from the existing dataframe.",\n'
#     '  "solution": "Reuse the dataframe, convert the date column to datetime, aggregate revenue by month, and plot the result.",\n'
#     '  "code": "import pandas as pd\\ntmp_df = df.copy()\\n...",\n'
#     '  "should_auto_execute": true\n'
#     "}\n"
#     "Return no extra text."
# )


BRAIN_PROMPT = """You are the brain of a notebook-native coding assistant.
Return ONLY valid JSON. 
Schema:
{
  "understood": string,
  "solution": string,
  "code": string,
  "should_auto_execute": boolean
}
Rules:
    - understood must be a short natural-language restatement of the request.
    - solution must explain the approach and mention key reuse decisions when relevant.
    - The solution field may use lightweight Markdown when useful for readability, such as short bullets, numbered steps, bold labels, and inline code.
    - Do not put executable code blocks in the solution field; executable Python belongs only in the code field.
    - code must be a raw Python code string, with no markdown fences.
    - should_auto_execute must be true or false.
    - Return ONLY valid JSON. Do not wrap the JSON in markdown fences or triple backticks.

    - Prefer reusing existing notebook symbols, imports, helper functions, classes, and objects whenever possible.
    - Do not invent unavailable symbols.
    - Avoid redefining existing symbols unless the request clearly asks for modification or replacement.
    - Keep simple tasks simple; do not introduce unnecessary abstraction.
    - Write code that is safe and easy to rerun in a notebook.

    - When loading, preparing, cleaning, analyzing, or plotting data, create clear reusable notebook symbols for likely follow-up work.
    - Prefer stable names for reusable objects, such as `df`, `<name>_df`, `analysis_df`, `numeric_cols`, `categorical_cols`, `feature_cols`, `target_col`, `metrics_df`, or clearly named helper functions.
    - If a derived variable is likely to be useful later, assign it to a named symbol rather than keeping it hidden inside a temporary expression.
    - For datasets, when useful, prepare reusable summaries such as column lists, dtype summaries, missing-value summaries, and derived analysis columns.
    - Do not create many unnecessary globals; create only symbols that are likely to support follow-up requests.
    - If you create reusable symbols, mention their names briefly in the solution.

    - When the task has multiple logical steps or is likely to be reused, prefer a small helper function with a descriptive name.
    - Use clear, suggestive names for new variables, functions, and classes.
    - Prefer classes only when the task naturally needs stateful or reusable structured behavior; otherwise prefer functions.
    - When defining a reusable function or class, include concise type hints when practical.
    - When defining a reusable function, add a short docstring if it improves notebook readability.
    - If the code primarily defines reusable functions or classes and would otherwise finish silently, print a short confirmation message naming the created symbols.

    - Prefer in-memory operations unless the user explicitly asks for file, shell, network, or other side-effecting actions.
    - If the user asks to show, display, inspect, or preview a result, explicitly render it with display(...) or print(...); do not rely on the last bare expression alone.
    - For tables, dataframes, and rich notebook objects, prefer display(...).
    - For matplotlib, create and render the figure explicitly with display(fig), then close it with plt.close(fig).
    - For Plotly, call fig.show().

    - If the request says not to run, generate preview-oriented code and set should_auto_execute to false.
    - If the task is ambiguous, choose the most conservative reasonable interpretation and write code that makes assumptions visible.
    - If the user asks for analysis ideas, explanation, planning, discussion, or no executable code, put the useful answer in solution using concise Markdown when helpful.
    - In that case, still return a valid code string containing only:
      "# No code generated because the user requested analysis/explanation only."
    - Set should_auto_execute to false. 
Example:
{
    "understood": "Plot the monthly revenue trend from the existing dataframe.",
    "solution": "Reuse the existing dataframe, convert the date column to datetime, aggregate revenue by month, and plot the result.",
    "code": "import pandas as pd\n\ndef build_monthly_revenue_trend(df: pd.DataFrame) -> pd.Series:\n    \"\"\"Aggregate revenue by calendar month.\"\"\"\n    tmp_df = df.copy()\n    tmp_df[\"date\"] = pd.to_datetime(tmp_df[\"date\"])\n    monthly_trend = tmp_df.groupby(tmp_df[\"date\"].dt.to_period(\"M\"))[\"revenue\"].sum()\n    monthly_trend.index = monthly_trend.index.astype(str)\n    return monthly_trend\n\nmonthly_trend = build_monthly_revenue_trend(df)\nmonthly_trend.plot(marker=\"o\", title=\"Monthly Revenue Trend\")",
    "should_auto_execute": true
}
Return no extra text.""".strip() 


REPAIR_PROMPT = (
    "You are repairing Python code for a notebook-native coding assistant after one failed auto-execution. "
    "Return ONLY valid JSON. "
    "Schema:\n"
    "{\n"
    '  "understood": string,\n'
    '  "solution": string,\n'
    '  "code": string,\n'
    '  "should_auto_execute": boolean\n'
    "}\n"
    "Rules:\n"
    "- Preserve the original user intent.\n"
    "- Reuse existing notebook symbols whenever possible.\n"
    "- Fix only what is needed to address the execution failure.\n"
    "- Do not invent unavailable symbols.\n"
    "- Do not add shell commands, package installs, network calls, or filesystem writes.\n"
    "- code must be a Python code string.\n"
    "- should_auto_execute must be true or false.\n"
    "- Do not return markdown.\n"
    "- Do not wrap JSON in triple backticks.\n"
    "Return no extra text."
)


PYTHON_ERROR_REVIEW_PROMPT = (
    "You are reviewing a Python cell written by the user that failed inside a notebook. "
    "Return ONLY valid JSON. "
    "Schema:\n"
    "{\n"
    '  "understood": string,\n'
    '  "solution": string,\n'
    '  "code": string\n'
    "}\n"
    "Rules:\n"
    "- Explain the user's likely intent briefly in 'understood'.\n"
    "- Explain the likely cause of the error and the fix in 'solution'.\n"
    "- Return a corrected Python code string in 'code'.\n"
    "- Reuse existing notebook symbols whenever possible.\n"
    "- Do not invent unavailable symbols.\n"
    "- Do not add shell commands, package installs, network calls, or filesystem writes.\n"
    "- The corrected code is for manual review only and will not be auto-executed.\n"
    "- Do not return markdown.\n"
    "- Do not wrap JSON in triple backticks.\n"
    "Return no extra text."
)


def _cfg_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _cfg_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _get_max_auto_repair_attempts(state) -> int:
    return max(0, _cfg_int(getattr(state.config, "max_auto_repair_attempts", 1), 1))


def _get_raise_on_failure(state) -> bool:
    return _cfg_bool(getattr(state.config, "raise_on_auto_exec_failure", False), False)


def _get_allow_repair_retry(state) -> bool:
    return _cfg_bool(getattr(state.config, "allow_repair_retry", True), True)


def _get_max_error_chars(state) -> int:
    return max(200, _cfg_int(getattr(state.config, "max_error_chars", 1200), 1200))


def _get_assist_on_python_error(state) -> bool:
    return _cfg_bool(getattr(state.config, "assist_on_python_error", True), True)



def _select_relevant_context(user_text: str) -> List[Dict[str, Any]]:
    state = get_state()
    items: List[Dict[str, Any]] = []

    # Include symbols from the registry, as they represent the most structured and up-to-date understanding of the notebook's available code elements. Score them based on name matches, metadata relevance, and recency of use to prioritize the most pertinent symbols for the user's request.
    for name, meta in state.symbol_registry.items():
        if meta.get("deleted"):
            continue

        score = 0
        if name.lower() in user_text.lower():
            score += 5

        symbol_text = " ".join(
            str(part) for part in [
                name,
                meta.get("kind", ""),
                meta.get("type", ""),
                meta.get("signature", ""),
                meta.get("docstring", ""),
                " ".join(meta.get("public_member_names", []) or []),
                " ".join(
                    f"{member} {sig}"
                    for member, sig in (meta.get("public_callable_signatures") or {}).items()
                ),
                meta.get("repr", ""),
            ] if part
        )

        score += score_overlap(user_text, symbol_text)
        score += max(0, 3 - (state.cell_counter - meta.get("last_seen_cell_id", state.cell_counter)))

        if score > 0:
            items.append(
                {
                    "kind": "symbol",
                    "symbol_kind": meta.get("kind", ""),
                    "name": name,
                    "type": meta.get("type", ""),
                    "repr": meta.get("repr", ""),
                    "provenance": meta.get("provenance", ""),
                    "signature": meta.get("signature"),
                    "docstring": meta.get("docstring"),
                    "public_member_names": meta.get("public_member_names"),
                    "public_callable_signatures": meta.get("public_callable_signatures"),
                    "score": score,
                }
            )

    # Include recent execution records, as they may contain relevant generated code, requests, or interpretations that aren't fully captured in the symbol registry. Look back at most 12 records to limit the scope to recent context. Score them based on overlap with the user text and recency, and include them if they have any relevance or if the user text contains references to previous executions.
    for record in reversed(state.exec_history[-12:]):
        descriptor = f"{record.get('request', '')} {record.get('understood', '')} {record.get('solution', '')}"
        score = score_overlap(user_text, descriptor)
        if score > 0 or any(word in user_text.lower() for word in ["that", "it", "previous", "last", "snippet"]):
            items.append(
                {
                    "kind": "exec",
                    "exec_id": record["exec_id"],
                    "name": f"exec_{record['exec_id']}",
                    "type": "generated_code",
                    "repr": short_repr(record.get("generated_code", ""), limit=120),
                    "score": score + 1,
                    "request": record.get("request", ""),
                }
            )

    # Include recent non-linked Python cells, as they may contain relevant code or context that hasn't been captured in the symbol registry or execution history. Exclude linked cells to avoid redundancy, since their content is likely already represented in the symbol registry or exec history.
    for cell in reversed(state.cell_history[-8:]):
        if cell.get("cell_kind") != "python":
            continue
        if cell.get("linked_exec_id") is not None:
            continue

        raw = cell.get("raw_text", "")
        score = score_overlap(user_text, raw)

        if score > 0 or any(
            word in user_text.lower()
            for word in ["plot", "figure", "fig", "trace", "plane", "previous", "last"]
        ):
            items.append(
                {
                    "kind": "cell",
                    "name": f"cell_{cell['cell_id']}",
                    "type": "recent_user_python_cell",
                    "cell_kind": cell.get("cell_kind"),
                    "status": cell.get("status"),
                    "repr": short_repr(raw, limit=240),
                    "score": score + 1,
                    "raw_text": raw,
                }
            )

    items.sort(key=lambda item: item["score"], reverse=True)
    return items[: state.config.max_context_items]
def _format_context_item_summary(item: Dict[str, Any]) -> str:
    kind = item.get("kind", "unknown")
    name = item.get("name", "<unnamed>")
    type_part = f" ({item.get('type', '')})" if item.get("type") else ""

    base = f"- {kind}: {name}{type_part}"

    if kind == "symbol":
        if item.get("symbol_kind"):
            base += f" [{item['symbol_kind']}]"
        if item.get("signature"):
            base += f" {item['signature']}"
        if item.get("docstring"):
            base += f" — {item['docstring']}"
        if item.get("symbol_kind") == "class" and item.get("public_member_names"):
            base += f" — members: {', '.join(item['public_member_names'])}"
        if item.get("symbol_kind") == "class" and item.get("public_callable_signatures"):
            method_bits = [
                f"{method_name}{sig}"
                for method_name, sig in item["public_callable_signatures"].items()
            ]
            base += f" — callables: {', '.join(method_bits)}"

    elif kind == "exec":
        if item.get("request"):
            base += f" — request: {item['request']}"
        if item.get("status"):
            base += f" — status: {item['status']}"

    elif kind == "cell":
        if item.get("status"):
            base += f" — status: {item['status']}"
        if item.get("cell_kind"):
            base += f" — cell_kind: {item['cell_kind']}"

    if item.get("repr"):
        base += f" — {item['repr']}"

    return base

def _summarize_context(user_text: str, context_items: List[Dict[str, Any]]) -> str:
    if not context_items:
        return "No prior notebook context looked necessary."
    
    state = get_state()
    default = {
        "summary": "\n".join(
            _format_context_item_summary(item)
            for item in context_items[: state.config.max_context_items]
        )
    }

    prompt = (
        "Summarize ONLY the selected notebook context in 2-4 important, concise bullets.\n"
        "Focus on facts useful for the next code-generation step.\n"
        "Do not answer the user request.\n"
        "Do not propose analysis steps.\n"
        "Do not add domain knowledge or likely next actions.\n"
        "Only mention facts grounded in the provided CONTEXT.\n"
        f"USER REQUEST:\n{user_text}\n\n"
        f"CONTEXT:\n{default['summary']}"
    )
    response = call_model(
        None,
        prompt,
        {"user_text": user_text, "context_items": context_items},
        default=default,
        role_name="summarizer",
        config=state.config,
    )

    if isinstance(response, dict):
        summary = response.get("summary", default["summary"])
    elif isinstance(response, str) and response.strip():
        summary = response.strip()
    elif isinstance(response, list):
        summary = "\n".join(f"- {str(x)}" for x in response)
    else:
        summary = default["summary"]

    if isinstance(summary, list):
        summary = "\n".join(f"- {str(x)}" for x in summary)

    return str(summary)


def _interpret_request(user_text: str, context_summary: str) -> Dict[str, Any]:
    state = get_state()
    default = {
        "understood": user_text.strip().rstrip("."),
        "intent": "preview" if explicit_no_run(user_text) else "solve",
        "task_type": "code_generation",
    }
    response = call_model(
        None,
        "Interpret this notebook request. Return JSON with keys: understood(what I(=LLM) understood), intent, task_type.",
        {"user_text": user_text, "context_summary": context_summary},
        default=default,
        role_name="interpreter",
        config=state.config,
    )
    
    return coerce_jsonish(response, default)



def _generate_code_demo_fallback(
    user_text: str,
    interpreted: Dict[str, Any],
    context_items: List[Dict[str, Any]],
    context_summary: str,
    user_ns: Dict[str, Any],
) -> Dict[str, Any]:
    no_run = explicit_no_run(user_text)

    imports = []
    if "np" not in user_ns:
        imports.append("import numpy as np")
    if "plt" not in user_ns:
        imports.append("import matplotlib.pyplot as plt")

    code = "\n".join(
        imports
        + [
            "",
            "# Demo fallback mode:",
            "# No brain model/API key is available, so this is a fixed sample,",
            "# not a real AI-generated answer to the request.",
            "x = np.linspace(0, 2 * np.pi, 400)",
            "y = np.sin(x)",
            "",
            "plt.figure(figsize=(8, 4))",
            "plt.plot(x, y)",
            "plt.title('Demo fallback: np.sin(x)')",
            "plt.xlabel('x')",
            "plt.ylabel('sin(x)')",
            "plt.grid(True)",
            "plt.show()",
        ]
    )

    return {
        "understood": interpreted["understood"],
        "solution": (
            "No brain model/API key is available. Demo fallback is enabled, "
            "so I am showing one fixed safe example: a simple np.sin(x) plot. "
            "This is not a real model-generated answer to your request."
        ),
        "code": code,
        "should_auto_execute": not no_run,
    }
def _generate_code_strict_scaffold(
    user_text: str,
    interpreted: Dict[str, Any],
    context_items: List[Dict[str, Any]],
    context_summary: str,
) -> Dict[str, Any]:
    code = "\n".join(
        [
            "# No brain model was available and demo fallback is disabled.",
            "# Wire OPENAI_API_KEY and BRAIN_MODEL, or enable allow_fallback_codegen for canned demos.",
            "# Selected context:",
            *(f"# - {item['kind']}: {item['name']} ({item.get('type', '')})" for item in context_items[:6]),
            "",
            "result = {",
            "    'request': " + repr(user_text) + ",",
            "    'interpreted': " + repr(interpreted) + ",",
            "    'context_summary': " + repr(context_summary) + ",",
            "}",
            "result",
        ]
    )
    return {
        "understood": interpreted["understood"],
        "solution": "No configured brain model was available, so this strict scaffold was returned instead of hidden hardcoded behavior.",
        "code": code,
        "should_auto_execute": False,
    }


def _validate_plan_or_default(raw_plan: Any, default_plan: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validated = CodePlan.model_validate(raw_plan)
        plan = validated.model_dump()
    except ValidationError:
        plan = dict(default_plan)
    plan["code"] = normalize_code(plan["code"])
    return plan


def _validate_error_review_or_default(raw_plan: Any, default_plan: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validated = ErrorReviewPlan.model_validate(raw_plan)
        plan = validated.model_dump()
    except ValidationError:
        plan = dict(default_plan)
    plan["code"] = normalize_code(plan["code"])
    return plan

NO_CODE_COMMENT = "# No code generated because the user requested analysis/explanation only."


def _is_no_code_request(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in [
            "no code",
            "without code",
            "don't create executable code",
            "do not create executable code",
            "dont create executable code",
            "just give me the analysis",
            "only give me the analysis",
            "analysis only",
            "explanation only",
            "planning only",
        ]
    )


def _generate_code(
    user_text: str,
    interpreted: Dict[str, Any],
    context_items: List[Dict[str, Any]],
    context_summary: str,
    user_ns: Dict[str, Any],
) -> Dict[str, Any]:
    state = get_state()
    brain_available = can_call_model(
        None,
        role_name="brain",
        config=state.config,
    )

    if not brain_available and state.config.allow_fallback_codegen:
        plan = _generate_code_demo_fallback(user_text, interpreted, context_items, context_summary, user_ns)
        plan["used_demo_fallback"] = True
        plan["model_used"] = None
        return plan

    strict_default = _generate_code_strict_scaffold(user_text, interpreted, context_items, context_summary)
    if not brain_available:
        strict_default["used_demo_fallback"] = False
        strict_default["model_used"] = None
        return strict_default

    response = call_model(
        None,
        textwrap.dedent(BRAIN_PROMPT),
        {
            "user_text": user_text,
            "interpreted": interpreted,
            "context_items": context_items,
            "context_summary": context_summary,
            "user_symbols": sorted(public_namespace(user_ns).keys()),
        },
        default=strict_default,
        role_name="brain",
        config=state.config,
    )
    raw_plan = coerce_jsonish(response, strict_default)
    plan = _validate_plan_or_default(raw_plan, strict_default)
    plan["used_demo_fallback"] = False
    plan["model_used"] = state.config.brain_model
    return plan


def _register_pending_proposal(code: str, source_exec_id: Optional[int]) -> int:
    state = get_state()
    proposal_id = state.next_proposal_id()
    state.pending_proposals.append(
        {
            "proposal_id": proposal_id,
            "source_exec_id": source_exec_id,
            "code": code,
            "normalized_code": normalize_code(code),
            "status": "pending",
            "created_at": utc_ts(),
        }
    )
    return proposal_id


def _create_exec_record(
    user_text: str,
    interpreted: Dict[str, Any],
    plan: Dict[str, Any],
    context_items: List[Dict[str, Any]],
    context_summary: str,
    decision_mode: str,
    safety_reasons: List[str],
) -> int:
    state = get_state()
    exec_id = state.next_exec_id()
    record = {
        "exec_id": exec_id,
        "request": user_text,
        "understood": plan.get("understood", interpreted.get("understood", user_text)),
        "solution": plan.get("solution", ""),
        "generated_code": plan.get("code", ""),
        "exec_mode": decision_mode,
        "status": "planned",
        "context_items": context_items,
        "context_summary": context_summary,
        "safety_reasons": safety_reasons,
        "provider": state.config.provider,
        "brain_model": plan.get("model_used"),
        "used_demo_fallback": plan.get("used_demo_fallback", False),
        "attempts": [],
        "repair_count": 0,
        "created_at": utc_ts(),
        "finished_at": None,
    }
    state.exec_history.append(record)
    if state.current_cell is not None:
        state.current_cell["linked_exec_id"] = exec_id
    return exec_id


def _get_exec_record(exec_id: int) -> Optional[Dict[str, Any]]:
    state = get_state()
    for record in reversed(state.exec_history):
        if record.get("exec_id") == exec_id:
            return record
    return None


def _append_attempt(
    record: Dict[str, Any],
    *,
    attempt_no: int,
    code: str,
    status: str,
    safety_mode: Optional[str],
    safety_reasons: Optional[List[str]],
    model_used: Optional[str],
    used_demo_fallback: bool,
    is_repair: bool,
    error: Optional[str] = None,
    error_type: Optional[str] = None,
    traceback_text: Optional[str] = None,
) -> None:
    record.setdefault("attempts", []).append(
        {
            "attempt": attempt_no,
            "is_repair": is_repair,
            "status": status,
            "code": code,
            "normalized_code": normalize_code(code),
            "safety_mode": safety_mode,
            "safety_reasons": safety_reasons or [],
            "model_used": model_used,
            "used_demo_fallback": used_demo_fallback,
            "error_type": error_type,
            "error": error,
            "traceback": traceback_text,
            "finished_at": utc_ts(),
        }
    )


def _finalize_exec_success(record: Dict[str, Any], *, code: str, solution: Optional[str] = None, understood: Optional[str] = None) -> None:
    record["status"] = "executed"
    record["generated_code"] = code
    if solution is not None:
        record["solution"] = solution
    if understood is not None:
        record["understood"] = understood
    record["finished_at"] = utc_ts()


def _finalize_exec_failure(record: Dict[str, Any], *, error_type: str, error_message: str, traceback_text: str) -> None:
    record["status"] = "error"
    record["error_type"] = error_type
    record["error"] = error_message
    record["traceback"] = traceback_text
    record["finished_at"] = utc_ts()


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _execute_code_once(*, code: str, exec_id: int, attempt_no: int, ip) -> Tuple[bool, Optional[Exception], str]:
    try:
        compiled = compile(code, filename=f"<auto_agent:{exec_id}:attempt:{attempt_no}>", mode="exec")
        exec(compiled, ip.user_ns, ip.user_ns)
        return True, None, ""
    except Exception as exc:  # noqa: BLE001
        return False, exc, traceback.format_exc()


def _build_repair_default(initial_plan: Dict[str, Any], error_message: str) -> Dict[str, Any]:
    return {
        "understood": str(initial_plan.get("understood", "Repair the previous notebook request.")),
        "solution": f"Repair attempt scaffold after failure: {error_message}",
        "code": "",
        "should_auto_execute": False,
    }


def _build_python_error_review_default(raw_code: str, error_message: str) -> Dict[str, Any]:
    return {
        "understood": "Review the failed Python cell and propose a corrected version for manual rerun.",
        "solution": f"The cell failed with {error_message}. A manual correction is proposed below.",
        "code": "\n".join(
            [
                "# Proposed manual fix scaffold.",
                f"# Original error: {error_message}",
                raw_code,
            ]
        ),
    }


def _generate_repair_plan(
    *,
    user_text: str,
    interpreted: Dict[str, Any],
    context_items: List[Dict[str, Any]],
    context_summary: str,
    failed_plan: Dict[str, Any],
    error_type: str,
    error_message: str,
    traceback_text: str,
    user_ns: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    state = get_state()
    brain_available = can_call_model(
        None,
        role_name="repair",
        config=state.config,
    )
    if not brain_available:
        return None

    repair_default = _build_repair_default(failed_plan, error_message)
    response = call_model(
        None,
        textwrap.dedent(REPAIR_PROMPT),
        {
            "user_text": user_text,
            "interpreted": interpreted,
            "context_items": context_items,
            "context_summary": context_summary,
            "user_symbols": sorted(public_namespace(user_ns).keys()),
            "previous_code": failed_plan.get("code", ""),
            "previous_understood": failed_plan.get("understood", ""),
            "previous_solution": failed_plan.get("solution", ""),
            "error_type": error_type,
            "error_message": error_message,
            "traceback": traceback_text,
        },
        default=repair_default,
        role_name="repair",
        config=state.config,
    )
    raw_plan = coerce_jsonish(response, repair_default)
    repaired = _validate_plan_or_default(raw_plan, repair_default)
    if not repaired.get("code"):
        return None
    if normalize_code(repaired["code"]) == normalize_code(failed_plan.get("code", "")):
        return None
    repaired["used_demo_fallback"] = False
    repaired["model_used"] = state.config.repair_model
    return repaired


def _generate_python_error_review(
    *,
    raw_code: str,
    error_type: str,
    error_message: str,
    traceback_text: str,
    user_ns: Dict[str, Any],
) -> Dict[str, Any]:
    state = get_state()
    review_request = (
        "Review this failed Python notebook cell, explain the likely problem briefly, "
        "and propose a corrected version for manual rerun."
    )
    context_items = _select_relevant_context(raw_code)
    context_summary = _summarize_context(review_request + "\n\n" + raw_code, context_items)
    default_review = _build_python_error_review_default(raw_code, error_message)

    brain_available = can_call_model(
        None,
        role_name="python_error_review",
        config=state.config,
    )
    if not brain_available:
        review = dict(default_review)
        review["model_used"] = None
        review["context_summary"] = context_summary
        return review

    response = call_model(
        None,
        textwrap.dedent(PYTHON_ERROR_REVIEW_PROMPT),
        {
            "raw_code": raw_code,
            "error_type": error_type,
            "error_message": error_message,
            "traceback": traceback_text,
            "user_symbols": sorted(public_namespace(user_ns).keys()),
            "context_items": context_items,
            "context_summary": context_summary,
        },
        default=default_review,
        role_name="python_error_review",
        config=state.config,
    )
    raw_review = coerce_jsonish(response, default_review)
    review = _validate_error_review_or_default(raw_review, default_review)
    review["model_used"] = state.config.python_error_review_model
    review["context_summary"] = context_summary
    return review


def handle_failed_python_cell_review(*, raw_code: str, error_obj: Any, user_ns: Dict[str, Any]) -> None:
    state = get_state()
    if not _get_assist_on_python_error(state):
        return

    try:
        error_type = type(error_obj).__name__ if error_obj is not None else "ExecutionError"
        error_message = _truncate_text(f"{error_type}: {error_obj}", _get_max_error_chars(state))
        traceback_text = _truncate_text(
            "".join(traceback.format_exception(type(error_obj), error_obj, error_obj.__traceback__)) if error_obj is not None else "",
            _get_max_error_chars(state),
        )
        review = _generate_python_error_review(
            raw_code=raw_code,
            error_type=error_type,
            error_message=error_message,
            traceback_text=traceback_text,
            user_ns=user_ns,
        )
        show_agent_panel(
            agent_name=f"{state.config.name} — Python error review",
            understood=review["understood"],
            observed_error=error_message,
            solution=review["solution"],
            code=review["code"],
            execution_label="preview only • suggested fix for your Python cell",
            context_summary=review.get("context_summary") if getattr(state.config, "echo_context", False) else None,
        )
        proposal_id = _register_pending_proposal(review["code"], None)
        show_message(
            "Suggested fix stored",
            f"This corrected code was stored as proposal #{proposal_id}. Review it, then copy and paste it into a normal Python cell if you want to run it.",
        )
    except Exception as exc:  # noqa: BLE001
        show_message("Python error review skipped", f"The assistant could not prepare a suggested fix: {short_repr(exc, limit=240)}")


def _execute_with_optional_retry(
    *,
    exec_id: int,
    user_text: str,
    interpreted: Dict[str, Any],
    context_items: List[Dict[str, Any]],
    context_summary: str,
    initial_plan: Dict[str, Any],
    initial_safety,
    ip,
) -> Tuple[bool, Optional[Exception]]:
    state = get_state()
    record = _get_exec_record(exec_id)
    if record is None:
        return False, RuntimeError(f"Execution record {exec_id} was not found.")

    max_error_chars = _get_max_error_chars(state)
    allow_repair_retry = _get_allow_repair_retry(state)
    max_repairs = _get_max_auto_repair_attempts(state)

    attempt_no = 1
    success, exc, tb_text = _execute_code_once(code=initial_plan["code"], exec_id=exec_id, attempt_no=attempt_no, ip=ip)
    if success:
        _append_attempt(
            record,
            attempt_no=attempt_no,
            code=initial_plan["code"],
            status="executed",
            safety_mode=getattr(initial_safety, "mode", None),
            safety_reasons=list(getattr(initial_safety, "reasons", []) or []),
            model_used=initial_plan.get("model_used"),
            used_demo_fallback=bool(initial_plan.get("used_demo_fallback", False)),
            is_repair=False,
        )
        _finalize_exec_success(
            record,
            code=initial_plan["code"],
            solution=initial_plan.get("solution"),
            understood=initial_plan.get("understood"),
        )
        return True, None

    error_type = type(exc).__name__ if exc is not None else "ExecutionError"
    error_message = _truncate_text(f"{error_type}: {exc}", max_error_chars)
    truncated_tb = _truncate_text(tb_text or "", max_error_chars)
    _append_attempt(
        record,
        attempt_no=attempt_no,
        code=initial_plan["code"],
        status="error",
        safety_mode=getattr(initial_safety, "mode", None),
        safety_reasons=list(getattr(initial_safety, "reasons", []) or []),
        model_used=initial_plan.get("model_used"),
        used_demo_fallback=bool(initial_plan.get("used_demo_fallback", False)),
        is_repair=False,
        error=error_message,
        error_type=error_type,
        traceback_text=truncated_tb,
    )

    if not allow_repair_retry or max_repairs <= 0:
        _finalize_exec_failure(record, error_type=error_type, error_message=error_message, traceback_text=truncated_tb)
        return False, exc

    show_message(
        "Auto-run failed",
        "Auto-run failed once. Trying one repair pass using the error details.",
    )

    user_ns = public_namespace(ip.user_ns)
    repaired_plan = _generate_repair_plan(
        user_text=user_text,
        interpreted=interpreted,
        context_items=context_items,
        context_summary=context_summary,
        failed_plan=initial_plan,
        error_type=error_type,
        error_message=error_message,
        traceback_text=truncated_tb,
        user_ns=user_ns,
    )
    if repaired_plan is None:
        _finalize_exec_failure(record, error_type=error_type, error_message=error_message, traceback_text=truncated_tb)
        show_message(
            "Repair failed",
            "Repair attempt could not produce a valid revised code plan. The original error was recorded in execution history.",
        )
        return False, exc

    repaired_safety = classify_execution(repaired_plan["code"])
    repair_attempt_no = 2
    record["repair_count"] = 1

    if getattr(repaired_safety, "mode", None) != "auto":
        blocked_reason = "Repair attempt produced code that is not eligible for safe auto-execution."
        _append_attempt(
            record,
            attempt_no=repair_attempt_no,
            code=repaired_plan["code"],
            status="blocked",
            safety_mode=getattr(repaired_safety, "mode", None),
            safety_reasons=list(getattr(repaired_safety, "reasons", []) or []) + [blocked_reason],
            model_used=repaired_plan.get("model_used"),
            used_demo_fallback=bool(repaired_plan.get("used_demo_fallback", False)),
            is_repair=True,
            error=blocked_reason,
            error_type="SafetyBlocked",
            traceback_text="",
        )
        _finalize_exec_failure(record, error_type="SafetyBlocked", error_message=blocked_reason, traceback_text=truncated_tb)
        show_message("Repair blocked", blocked_reason)
        return False, RuntimeError(blocked_reason)

    show_message(
        "Repair attempt",
        f"A repaired version was generated via {repaired_plan.get('model_used') or 'configured brain model'}. Re-running safety check and executing once.",
    )

    repair_success, repair_exc, repair_tb = _execute_code_once(
        code=repaired_plan["code"],
        exec_id=exec_id,
        attempt_no=repair_attempt_no,
        ip=ip,
    )
    if repair_success:
        _append_attempt(
            record,
            attempt_no=repair_attempt_no,
            code=repaired_plan["code"],
            status="executed",
            safety_mode=getattr(repaired_safety, "mode", None),
            safety_reasons=list(getattr(repaired_safety, "reasons", []) or []),
            model_used=repaired_plan.get("model_used"),
            used_demo_fallback=bool(repaired_plan.get("used_demo_fallback", False)),
            is_repair=True,
        )
        _finalize_exec_success(
            record,
            code=repaired_plan["code"],
            solution=repaired_plan.get("solution"),
            understood=repaired_plan.get("understood"),
        )
        show_message("Repair succeeded", "Repair succeeded on the second attempt.")
        return True, None

    repair_error_type = type(repair_exc).__name__ if repair_exc is not None else "ExecutionError"
    repair_error_message = _truncate_text(f"{repair_error_type}: {repair_exc}", max_error_chars)
    repair_truncated_tb = _truncate_text(repair_tb or "", max_error_chars)
    _append_attempt(
        record,
        attempt_no=repair_attempt_no,
        code=repaired_plan["code"],
        status="error",
        safety_mode=getattr(repaired_safety, "mode", None),
        safety_reasons=list(getattr(repaired_safety, "reasons", []) or []),
        model_used=repaired_plan.get("model_used"),
        used_demo_fallback=bool(repaired_plan.get("used_demo_fallback", False)),
        is_repair=True,
        error=repair_error_message,
        error_type=repair_error_type,
        traceback_text=repair_truncated_tb,
    )
    _finalize_exec_failure(
        record,
        error_type=repair_error_type,
        error_message=repair_error_message,
        traceback_text=repair_truncated_tb,
    )
    show_message(
        "Repair failed",
        "Repair attempt also failed. The final error was recorded in execution history.",
    )
    return False, repair_exc


def __auto_agent_handle__(user_text: str):
    state = get_state()
    try:
        from IPython import get_ipython  # noqa: WPS433

        ip = get_ipython()
    except Exception:
        ip = None

    user_ns = public_namespace(ip.user_ns if ip is not None else {})
    context_items = _select_relevant_context(user_text)
    context_summary = _summarize_context(user_text, context_items)
    interpreted = _interpret_request(user_text, context_summary)
    plan = _generate_code(user_text, interpreted, context_items, context_summary, user_ns)

    safety = classify_execution(plan["code"])
    requested_no_run = explicit_no_run(user_text)
    requested_run = explicit_run(user_text)

    decision_mode = "manual"
    if requested_no_run:
        decision_mode = "manual"
    elif requested_run and state.config.auto_execute and safety.mode == "auto":
        decision_mode = "auto"
    elif state.config.auto_execute and plan.get("should_auto_execute") and safety.mode == "auto":
        decision_mode = "auto"

    source_label = (
        f"auto-execute via {plan.get('model_used')}"
        if decision_mode == "auto" and plan.get("model_used")
        else "auto-execute demo fallback"
        if decision_mode == "auto" and plan.get("used_demo_fallback")
        else "preview only"
    )
    show_agent_panel(
        agent_name=state.config.name,
        understood=plan["understood"],
        solution=plan["solution"],
        code=plan["code"],
        execution_label=source_label,
        context_summary=context_summary if state.config.echo_context else None,
        safety_reasons=safety.reasons[:3],
    )

    exec_id = _create_exec_record(
        user_text=user_text,
        interpreted=interpreted,
        plan=plan,
        context_items=context_items,
        context_summary=context_summary,
        decision_mode=decision_mode,
        safety_reasons=safety.reasons,
    )

    if decision_mode != "auto":
        proposal_id = _register_pending_proposal(plan["code"], exec_id)
        show_message(
            "Manual step",
            f"This code was stored as proposal #{proposal_id}. If you copy it into a normal Python cell and run it, the historian will mark it as agent_proposed_then_user_executed.",
        )
        return None

    if ip is None:
        show_message("Execution skipped", "No active IPython runtime was detected.")
        return None

    success, final_error = _execute_with_optional_retry(
        exec_id=exec_id,
        user_text=user_text,
        interpreted=interpreted,
        context_items=context_items,
        context_summary=context_summary,
        initial_plan=plan,
        initial_safety=safety,
        ip=ip,
    )
    if success:
        return None

    if final_error is not None and _get_raise_on_failure(state):
        raise final_error
    return None
