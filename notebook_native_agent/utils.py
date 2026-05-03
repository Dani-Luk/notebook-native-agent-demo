from __future__ import annotations

import ast
import json
import os
import re
import textwrap
from typing import Any, Dict, List, Optional
import inspect

try:
    from .config_env import load_env_file
except Exception:  # pragma: no cover
    def load_env_file() -> None:
        return None

load_env_file()


def short_repr(value: Any, limit: int = 120) -> str:
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def public_namespace(user_ns: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in user_ns.items() if not k.startswith("_") and k not in {"In", "Out", "get_ipython", "exit", "quit"}}


def tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text.lower())


def score_overlap(a: str, b: str) -> int:
    sa = set(tokenize(a))
    sb = set(tokenize(b))
    return len(sa & sb)


def normalize_code(code: str) -> str:
    code = textwrap.dedent(code or "").strip()
    lines = [line.rstrip() for line in code.splitlines()]
    return "\n".join(lines).strip()


def explicit_no_run(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ["don't run", "do not run", "dont run", "preview only", "just show", "only show"])


def explicit_run(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ["run it", "execute", "go ahead", "please run", "do it"])


def coerce_jsonish(value: Any, default: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(value, dict):
        result = default.copy()
        result.update(value)
        return result
    if isinstance(value, str):
        stripped = value.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                result = default.copy()
                result.update(parsed)
                return result
        except Exception:
            pass
    return default.copy()


def namespace_snapshot(user_ns: Dict[str, Any], repr_limit: int = 160) -> Dict[str, Dict[str, str]]:
    snap: Dict[str, Dict[str, str]] = {}
    for name, value in public_namespace(user_ns).items():
        try:
            value_type = type(value).__name__
        except Exception:
            value_type = "unknown"

        if value_type == "module":
            module_name = getattr(value, "__name__", name)
            safe_repr = f"<module {module_name}>"
        else:
            safe_repr = short_repr(value, limit=repr_limit)

        snap[name] = {
            "type": value_type,
            "repr": safe_repr,
        }
    return snap


def diff_snapshots(before: Dict[str, Dict[str, str]], after: Dict[str, Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    created = []
    modified = []
    deleted = []
    for name, meta in after.items():
        if name not in before:
            created.append({"name": name, **meta})
        elif before[name] != meta:
            modified.append({"name": name, **meta})
    for name, meta in before.items():
        if name not in after:
            deleted.append({"name": name, **meta})
    return {"created": created, "modified": modified, "deleted": deleted}


def classify_python_syntax(raw_text: str) -> bool:
    text = (raw_text or "").strip()
    if not text:
        return True

    if text.startswith(("%", "!", "?", ";")):
        return True

    # Preserve normal IPython object introspection:
    # df?, np.array?, my_obj??, package.module.func?
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\?{1,2}", text):
        return True

    try:
        ast.parse(text)
        return True
    except SyntaxError:
        return False


def count_matplotlib_figures(user_ns: Dict[str, Any]) -> int:
    try:
        import matplotlib.pyplot as plt  # noqa: WPS433
        return len(list(map(str, plt.get_fignums())))
    except Exception:
        return 0


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def get_openai_api_key(api_key_env: str = "OPENAI_API_KEY") -> Optional[str]:
    key = os.getenv(api_key_env)
    return key.strip() if key else None


def _resolve_model_request(
    model_name: Optional[str] = None,
    *,
    role_name: Optional[str] = None,
    config: Any = None,
    provider: str = "openai",
    api_key_env: str = "OPENAI_API_KEY",
    model_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if role_name and config is not None and hasattr(config, "get_role_settings"):
        resolved = dict(config.get_role_settings(role_name))
        resolved.setdefault("model", model_name)
        resolved.setdefault("provider", getattr(config, "provider", provider))
        resolved.setdefault("api_key_env", getattr(config, "openai_api_key_env", api_key_env))
        return resolved

    resolved = dict(model_settings or {})
    resolved.setdefault("model", model_name)
    resolved.setdefault("provider", provider)
    resolved.setdefault("api_key_env", api_key_env)
    return resolved


def can_call_model(
    model_name: Optional[str] = None,
    provider: str = "openai",
    api_key_env: str = "OPENAI_API_KEY",
    *,
    role_name: Optional[str] = None,
    config: Any = None,
    model_settings: Optional[Dict[str, Any]] = None,
) -> bool:
    resolved = _resolve_model_request(
        model_name,
        role_name=role_name,
        config=config,
        provider=provider,
        api_key_env=api_key_env,
        model_settings=model_settings,
    )
    if resolved.get("enabled") is False:
        return False
    actual_model = resolved.get("model")
    actual_provider = resolved.get("provider", provider)
    actual_api_key_env = resolved.get("api_key_env", api_key_env)
    if not actual_model:
        return False
    if actual_provider != "openai":
        return False
    if not get_openai_api_key(actual_api_key_env):
        return False
    try:
        import openai  # noqa: F401,WPS433
    except Exception:
        return False
    return True


def _extract_openai_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text
    parts: List[str] = []
    output = getattr(response, "output", None) or []
    for item in output:
        for content in getattr(item, "content", []) or []:
            candidate = getattr(content, "text", None)
            if candidate:
                parts.append(candidate)
    return "\n".join(parts).strip()


def _openai_request_kwargs(resolved: Dict[str, Any]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    if resolved.get("top_p") is not None:
        kwargs["top_p"] = resolved["top_p"]
    if resolved.get("reasoning_effort"):
        kwargs["reasoning"] = {"effort": resolved["reasoning_effort"]}
    if resolved.get("verbosity"):
        kwargs["text"] = {"verbosity": resolved["verbosity"]}
    return kwargs


def call_model(
    model_name: Optional[str], # legacy / ad-hoc override
    prompt: str,
    payload: Dict[str, Any],
    default: Any,
    *,
    provider: str = "openai",
    api_key_env: str = "OPENAI_API_KEY",
    role_name: Optional[str] = None, # preferred
    config: Any = None,
    model_settings: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Call the configured model and return response text, or `default` if unavailable.

    Backward-compatible usage:
        call_model(model_name, prompt, payload, default, provider=..., api_key_env=...)

    Preferred usage with merged AgentConfig:
        call_model(None, prompt, payload, default, role_name="brain", config=state.config)
    """
    resolved = _resolve_model_request(
        model_name,
        role_name=role_name,
        config=config,
        provider=provider,
        api_key_env=api_key_env,
        model_settings=model_settings,
    )
    if not can_call_model(
        resolved.get("model"),
        provider=resolved.get("provider", provider),
        api_key_env=resolved.get("api_key_env", api_key_env),
        model_settings=resolved,
    ):
        return default

    try:
        from openai import OpenAI  # noqa: WPS433

        client = OpenAI(api_key=get_openai_api_key(resolved.get("api_key_env", api_key_env)))
        response = client.responses.create(
            model=resolved["model"],
            input=(
                prompt.strip()
                + "\n\nPAYLOAD JSON:\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            ),
            **_openai_request_kwargs(resolved),
        )
        text = _extract_openai_text(response)
        return text if text else default
    except Exception as ex:
        print (f"Error calling model {resolved.get('model')}: {ex}")
        return default


def safe_signature_text(value: Any) -> Optional[str]:
    try:
        return str(inspect.signature(value))
    except Exception:
        return None


def safe_docstring(value: Any, max_chars: int = 240) -> Optional[str]:
    try:
        doc = inspect.getdoc(value)
    except Exception:
        return None
    if not doc:
        return None
    doc = doc.strip()
    return doc if len(doc) <= max_chars else doc[: max_chars - 3] + "..."

def safe_public_member_names(value: Any) -> Optional[List[str]]:
    try:
        return sorted(name for name in dir(value) if not name.startswith("_"))
    except Exception:
        return None

def safe_public_callable_signatures(value: Any) -> Optional[Dict[str, str]]:
    try:
        result: Dict[str, str] = {}

        for name in dir(value):
            if name.startswith("_"):
                continue

            member = getattr(value, name, None)
            if not callable(member):
                continue

            sig = safe_signature_text(member)
            if not sig:
                continue

            # Optional nicety for class objects: hide leading self/cls
            try:
                if inspect.isclass(value):
                    params = list(inspect.signature(member).parameters.values())
                    if params and params[0].name in {"self", "cls"}:
                        sig = "(" + ", ".join(str(p) for p in params[1:]) + ")"
            except Exception:
                pass

            result[name] = sig

        return dict(sorted(result.items()))
    except Exception:
        return None

def minimal_symbol_metadata(value: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}

    if inspect.isfunction(value) or inspect.ismethod(value):
        meta["kind"] = "function"
        meta["signature"] = safe_signature_text(value)
        meta["docstring"] = safe_docstring(value)
        return meta

    if inspect.isclass(value):
        meta["kind"] = "class"
        meta["signature"] = safe_signature_text(value)
        meta["docstring"] = safe_docstring(value)
        meta["public_member_names"] = safe_public_member_names(value)
        meta["public_callable_signatures"] = safe_public_callable_signatures(value)
        return meta

    return meta
