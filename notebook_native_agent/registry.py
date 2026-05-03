from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_ROLE_MODELS = {
    "classifier": "gpt-5.4-nano",
    "interpreter": "gpt-5.4-mini",
    "summarizer": "gpt-5.4-mini",
    "brain": "gpt-5.4",
    "repair": "gpt-5.4",
    "python_error_review": "gpt-5.4-mini",
}


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _load_json_config(path: str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_openai_role_config(path: str = "openai.config.json") -> Dict[str, Dict[str, Any]]:
    raw = _load_json_config(path)
    return raw if isinstance(raw, dict) else {}


@dataclass
class RoleConfig:
    model: str
    enabled: bool = True
    top_p: Optional[float] = None
    reasoning_effort: Optional[str] = None
    verbosity: Optional[str] = None

    @classmethod
    def from_sources(
        cls,
        *,
        role_name: str,
        json_data: Optional[Dict[str, Any]],
    ) -> "RoleConfig":
        json_data = json_data or {}
        model = str(
            json_data.get("model")
            or DEFAULT_ROLE_MODELS.get(role_name, "gpt-5.4-mini")
        ).strip()

        def _as_float(name: str) -> Optional[float]:
            value = json_data.get(name)
            if value is None:
                return None
            try:
                return float(value)
            except Exception:
                return None

        return cls(
            model=model,
            enabled=bool(json_data.get("enabled", True)),
            top_p=_as_float("top_p"),
            reasoning_effort=(
                str(json_data.get("reasoning_effort")).strip()
                if json_data.get("reasoning_effort") is not None
                else None
            ),
            verbosity=(
                str(json_data.get("verbosity")).strip()
                if json_data.get("verbosity") is not None
                else None
            ),
        )

    def to_request_kwargs(self) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "model": self.model,
            "enabled": self.enabled,
        }
        if self.top_p is not None:
            request["top_p"] = self.top_p
        if self.reasoning_effort:
            request["reasoning_effort"] = self.reasoning_effort
        if self.verbosity:
            request["verbosity"] = self.verbosity
        return request


@dataclass
class AgentConfig:
    name: str = "Notebook Native Agent"
    provider: str = "openai"
    openai_api_key_env: str = "OPENAI_API_KEY"
    auto_execute: bool = True
    allow_fallback_codegen: bool = False
    use_model_classifier: bool = False
    echo_context: bool = True
    max_context_items: int = 8
    max_repr_chars: int = 160
    allow_repair_retry: bool = True
    max_auto_repair_attempts: int = 1
    raise_on_auto_exec_failure: bool = False
    max_error_chars: int = 1200
    assist_on_python_error: bool = True
    provider_config_path: str = "openai.config.json"
    roles: Dict[str, RoleConfig] = field(default_factory=dict)

    @property
    def classifier_model(self) -> str:
        return self.get_role_settings("classifier").get("model", DEFAULT_ROLE_MODELS["classifier"])

    @property
    def interpreter_model(self) -> str:
        return self.get_role_settings("interpreter").get("model", DEFAULT_ROLE_MODELS["interpreter"])

    @property
    def summarizer_model(self) -> str:
        return self.get_role_settings("summarizer").get("model", DEFAULT_ROLE_MODELS["summarizer"])

    @property
    def brain_model(self) -> str:
        return self.get_role_settings("brain").get("model", DEFAULT_ROLE_MODELS["brain"])

    @property
    def repair_model(self) -> str:
        return self.get_role_settings("repair").get("model", DEFAULT_ROLE_MODELS["repair"])

    @property
    def python_error_review_model(self) -> str:
        return self.get_role_settings("python_error_review").get("model", DEFAULT_ROLE_MODELS["python_error_review"])

    def get_role_settings(self, role_name: str) -> Dict[str, Any]:
        role = self.roles.get(role_name)
        if role is None:
            return {
                "model": DEFAULT_ROLE_MODELS.get(role_name, "gpt-5.4-mini"),
                "enabled": True,
            }
        return role.to_request_kwargs()

    @classmethod
    def from_sources(
        cls,
        provider_config_path: Optional[str] = None,
        runtime_config_path: Optional[str] = None,
    ) -> "AgentConfig":

        provider_config_path = provider_config_path or "openai.config.json"
        runtime_config_path = runtime_config_path or "notebook_native_agent.config.json"

        provider_roles = _load_openai_role_config(provider_config_path)
        runtime_cfg = _load_json_config(runtime_config_path)

        roles: Dict[str, RoleConfig] = {}
        for role_name in DEFAULT_ROLE_MODELS:
            roles[role_name] = RoleConfig.from_sources(
                role_name=role_name,
                json_data=provider_roles.get(role_name),
            )

        return cls(
            name=str(runtime_cfg.get("name", "Notebook Native Agent")).strip(),
            provider="openai",
            openai_api_key_env="OPENAI_API_KEY",
            auto_execute=bool(runtime_cfg.get("auto_execute", True)),
            allow_fallback_codegen=bool(runtime_cfg.get("allow_fallback_codegen", False)),
            use_model_classifier=bool(runtime_cfg.get("use_model_classifier", False)),
            echo_context=bool(runtime_cfg.get("echo_context", True)),
            max_context_items=_as_int(runtime_cfg.get("max_context_items", 10), 10),
            max_repr_chars=_as_int(runtime_cfg.get("max_repr_chars", 200), 200),
            allow_repair_retry=bool(runtime_cfg.get("allow_repair_retry", True)),
            max_auto_repair_attempts=_as_int(runtime_cfg.get("max_auto_repair_attempts", 1), 1),
            raise_on_auto_exec_failure=bool(runtime_cfg.get("raise_on_auto_exec_failure", False)),
            max_error_chars=_as_int(runtime_cfg.get("max_error_chars", 1600), 1600),
            assist_on_python_error=bool(runtime_cfg.get("assist_on_python_error", True)),
            provider_config_path=provider_config_path,
            roles=roles,
        )


@dataclass
class AgentState:
    config: AgentConfig = field(default_factory=AgentConfig.from_sources)
    started: bool = False
    paused: bool = False
    cell_counter: int = 0
    exec_counter: int = 0
    proposal_counter: int = 0
    cell_history: List[Dict[str, Any]] = field(default_factory=list)
    exec_history: List[Dict[str, Any]] = field(default_factory=list)
    symbol_registry: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    artifact_registry: List[Dict[str, Any]] = field(default_factory=list)
    pending_proposals: List[Dict[str, Any]] = field(default_factory=list)
    current_cell: Optional[Dict[str, Any]] = None
    hooks: Dict[str, Any] = field(default_factory=dict)

    def next_cell_id(self) -> int:
        self.cell_counter += 1
        return self.cell_counter

    def next_exec_id(self) -> int:
        self.exec_counter += 1
        return self.exec_counter

    def next_proposal_id(self) -> int:
        self.proposal_counter += 1
        return self.proposal_counter


_STATE = AgentState()


def get_state() -> AgentState:
    return _STATE


def reset_state(config: Optional[AgentConfig] = None) -> AgentState:
    global _STATE
    _STATE = AgentState(config=config or AgentConfig.from_sources())
    return _STATE