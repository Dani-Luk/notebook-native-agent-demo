from __future__ import annotations

from html import escape
from typing import Optional
from uuid import uuid4

from .handler import __auto_agent_handle__
from .historian import build_post_run_hook, build_pre_run_hook
from .registry import AgentConfig, get_state, reset_state
from .router import build_input_transformer
from .display import show_message


def _bool_label(value: bool) -> str:
    return "on" if bool(value) else "off"


def _pill(label: str, value: str, *, tone: str = "neutral") -> str:
    tones = {
        "neutral": ("#f3f4f6", "#d1d5db", "#111827"),
        "good": ("#ecfdf5", "#a7f3d0", "#065f46"),
        "warn": ("#fff7ed", "#fed7aa", "#9a3412"),
        "info": ("#eff6ff", "#bfdbfe", "#1d4ed8"),
    }
    bg, border, color = tones.get(tone, tones["neutral"])
    return (
        f"<span style='display:inline-flex;gap:6px;align-items:center;"
        f"padding:6px 10px;border-radius:999px;border:1px solid {border};"
        f"background:{bg};color:{color};font-size:12px;font-weight:600;'>"
        f"<span style='opacity:.8'>{escape(label)}</span>"
        f"<span>{escape(value)}</span>"
        f"</span>"
    )

def _welcome_copy_assets(root_id: str) -> str:
    return f"""
    <style>
      #{root_id} .auto-agent-example-card {{
        position: relative;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 11px 82px 11px 14px;
        background: linear-gradient(180deg,#ffffff 0%,#fafafa 100%);
        box-shadow: 0 1px 1px rgba(0,0,0,0.02);
      }}

      #{root_id} .auto-agent-example-text {{
        font-family: ui-monospace,SFMono-Regular,Menlo,monospace;
        font-size: 14px;
        line-height: 1.45;
        color: #111827;
        white-space: pre-wrap;
      }}

      #{root_id} .auto-agent-copy-btn {{
        position: absolute;
        top: 8px;
        right: 10px;
        border: 1px solid #d1d5db;
        background: #ffffff;
        color: #374151;
        border-radius: 8px;
        padding: 4px 8px;
        font-size: 12px;
        cursor: pointer;
        line-height: 1.2;
      }}

      #{root_id} .auto-agent-copy-btn:hover {{
        background: #f3f4f6;
      }}
      
    </style>

    <script>
      (function() {{
        const root = document.getElementById('{root_id}');
        if (!root || root.dataset.copyReady === '1') return;
        root.dataset.copyReady = '1';

        async function copyText(text) {{
          try {{
            if (navigator.clipboard && navigator.clipboard.writeText) {{
              await navigator.clipboard.writeText(text);
              return true;
            }}
          }} catch (err) {{
            // Kaggle may block Clipboard API via iframe permissions policy.
          }}

          try {{
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            ta.style.top = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();

            const ok = document.execCommand('copy');
            ta.remove();
            return ok;
          }} catch (err) {{
            return false;
          }}
        }}

        root.addEventListener('click', async function(event) {{
          const btn = event.target.closest('.auto-agent-copy-btn');
          if (!btn || !root.contains(btn)) return;

          const targetId = btn.getAttribute('data-copy-target');
          const textEl = targetId ? document.getElementById(targetId) : null;
          if (!textEl) return;

          const text = textEl.innerText || textEl.textContent || '';
          const old = btn.innerText;

          const ok = await copyText(text);
          btn.innerText = ok ? '✓ copied' : 'copy failed';
          setTimeout(() => btn.innerText = old, 1200);
        }});
      }})();
    </script>
    """

def _example_card(text: str) -> str:
    text_id = f"auto-agent-example-{uuid4().hex}"
    return f"""
    <div class='auto-agent-example-card'>
      <div id='{text_id}' class='auto-agent-example-text'>{escape(text)}</div>
      <button
        class='auto-agent-copy-btn'
        type='button'
        data-copy-target='{text_id}'
        title='Copy example prompt'
      >⧉ copy</button>
    </div>
    """


def _show_welcome_screen(state) -> None:
    """
    Display the welcome screen for the notebook agent.

    Args:
        state: The current AgentState.
    """
    try:
        from IPython.display import HTML, display  # noqa: WPS433
    except Exception:
        print(f"{state.config.name} started.")
        print("Notebook agent is active and watching all cells.")
        return

    strict_mode = not bool(state.config.allow_fallback_codegen)
    if strict_mode:
        mode_title = "Strict mode"
        mode_text = "Real model/config required for code generation. Demo fallback is disabled."
        mode_bg = "#eff6ff"
        mode_border = "#bfdbfe"
        mode_color = "#1d4ed8"
    else:
        mode_title = "Fallback mode"
        mode_text = (
            "Demo fallback is enabled. If no brain model/API key is available, "
            "the agent shows one fixed safe example: a graph of the sine function."
        )
        mode_bg = "#f0fdf4"
        mode_border = "#bbf7d0"
        mode_color = "#166534"

    auto_tone = "good" if bool(state.config.auto_execute) else "warn"
    fallback_tone = "warn" if strict_mode else "good"
    classifier_tone = "info" if bool(state.config.use_model_classifier) else "neutral"
    welcome_id = f"auto-agent-welcome-{uuid4().hex}"

    html = f"""
    <div id='{welcome_id}' style='font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
                border:1px solid #e5e7eb;border-radius:22px;padding:22px 22px 18px 22px;
                background:linear-gradient(180deg,#ffffff 0%,#fbfbfc 100%);
                box-shadow:0 10px 30px rgba(17,24,39,0.05);color:#111827;'>
      
      {_welcome_copy_assets(welcome_id)}                

      <div style='display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-bottom:16px;'>
        <div style='min-width:280px;flex:1 1 380px;'>
          <div style='display:inline-flex;align-items:center;gap:8px;
                      padding:6px 10px;border-radius:999px;border:1px solid #dbeafe;
                      background:#eff6ff;color:#1d4ed8;font-size:12px;font-weight:700;
                      letter-spacing:.02em;margin-bottom:12px;'>
            <span>⚡</span>
            <span>Notebook agent active</span>
          </div>
          <div style='font-size:20px;font-weight:800;line-height:1.2;margin-bottom:8px;'>
            {escape(state.config.name)}
          </div>
          <div style='font-size:14px;line-height:1.5;color:#4b5563;max-width:760px;'>
            Write Python normally, or write a natural-language request in a cell.
            The agent shares the live notebook context, proposes code, and can safely auto-run allowed cases.
          </div>
        </div>

        <div style='display:flex;gap:8px;flex-wrap:nowrap;justify-content:flex-end;flex:0 1 520px;'>
          {_pill('provider:', str(state.config.provider), tone='info')}
          {_pill('auto-execute:', _bool_label(state.config.auto_execute), tone=auto_tone)}
          {_pill('fallback:', _bool_label(state.config.allow_fallback_codegen), tone=fallback_tone)}
          {_pill('LLM cell classifier:', _bool_label(state.config.use_model_classifier), tone=classifier_tone)}
        </div>
      </div>

      <div style='display:grid;grid-template-columns:minmax(320px,1.15fr) minmax(260px,.85fr);gap:16px;align-items:start;'>
        <div style='border:1px solid #e5e7eb;border-radius:18px;padding:16px;background:#ffffff;'>
          <div style='font-size:15px;font-weight:800;margin-bottom:10px;'>Try a natural-language cell like:</div>
          <div style='display:grid;gap:10px;'>
            {_example_card('show me a funny fractal')}
            {_example_card('plot this: z = sin(x) * cos(y) (use plotly)')}
            {_example_card('I have this: tips.csv')}
          </div>
        </div>

        <div style='display:grid;gap:12px;'>
          <div style='border:1px solid #e5e7eb;border-radius:18px;padding:16px;background:#ffffff;'>
            <div style='font-size:15px;font-weight:800;margin-bottom:10px;'>How it works</div>
            <div style='display:grid;gap:10px;'>
              <div style='display:flex;gap:10px;align-items:flex-start;'>
                <div style='width:24px;height:24px;border-radius:999px;background:#111827;color:white;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:0 0 24px;'>1</div>
                <div style='font-size:14px;color:#374151;line-height:1.45;'><b>Stay in the notebook</b> — write Python or natural-language requests directly in code cells; the router turns non-Python text into agent requests.</div>
              </div>
              <div style='display:flex;gap:10px;align-items:flex-start;'>
                <div style='width:24px;height:24px;border-radius:999px;background:#111827;color:white;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:0 0 24px;'>2</div>
                <div style='font-size:14px;color:#374151;line-height:1.45;'><b>Work with live context</b> — the agent tracks notebook symbols, reusable helpers, object summaries, and prior executions.</div>
              </div>
              <div style='display:flex;gap:10px;align-items:flex-start;'>
                <div style='width:24px;height:24px;border-radius:999px;background:#111827;color:white;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:0 0 24px;'>3</div>
                <div style='font-size:14px;color:#374151;line-height:1.45;'><b>Preview or auto-run</b> — generated code is shown, safety-checked, tracked, and auto-run only when allowed.</div>
              </div>
            </div>
          </div>

          <div style='border:1px solid {mode_border};border-radius:18px;padding:14px 16px;background:{mode_bg};'>
            <div style='font-size:14px;font-weight:800;color:{mode_color};margin-bottom:6px;'>{escape(mode_title)}</div>
            <div style='font-size:14px;line-height:1.5;color:{mode_color};'>{escape(mode_text)}</div>
          </div>
        </div>
      </div>
    </div>
    """
    display(HTML(html))


def _get_ipython_shell() -> Any:
    """
    Return the active IPython shell.

    The notebook agent depends on IPython/Jupyter hooks, so startup should fail
    clearly when called outside an interactive notebook runtime.
    """
    try:
        from IPython import get_ipython  # noqa: WPS433
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("start_agent() requires IPython/Jupyter.") from exc

    ip = get_ipython()
    if ip is None:
        raise RuntimeError("No active IPython shell was found.")

    return ip


def _detach_agent_hooks(state, *, remove_handler: bool = False) -> None:
    """
    Best-effort removal of hooks currently registered by the agent.

    This is intentionally tolerant: IPython event unregistering can fail if a
    hook was already removed or if the frontend/runtime changed. In that case,
    stopping/restarting the agent should still continue gracefully.

    Args:
        state:
            Current AgentState.
        remove_handler:
            If True, also remove __auto_agent_handle__ from the notebook
            namespace when it still points to this package's handler.
    """
    hooks = state.hooks or {}
    ip = hooks.get("ip")

    if ip is None:
        return

    transformer = hooks.get("transformer")
    for attr in ("input_transformers_cleanup", "input_transformers_post"):
        transformers = getattr(ip, attr, [])
        if transformer in transformers:
            transformers.remove(transformer)

    pre_hook = hooks.get("pre_run_cell")
    post_hook = hooks.get("post_run_cell")

    try:
        if pre_hook is not None:
            ip.events.unregister("pre_run_cell", pre_hook)
    except Exception:
        pass

    try:
        if post_hook is not None:
            ip.events.unregister("post_run_cell", post_hook)
    except Exception:
        pass

    if remove_handler and ip.user_ns.get("__auto_agent_handle__") is __auto_agent_handle__:
        ip.user_ns.pop("__auto_agent_handle__", None)


def start_agent(
    config: Optional[AgentConfig] = None,
    *,
    show_welcome: bool = True,
    return_state: bool = False,
):
    """
    Cold-start the notebook agent and register its notebook hooks.

    This initializes a fresh AgentState, registers the input transformer that
    routes non-Python cells to the agent, registers pre/post execution hooks for
    notebook memory tracking, and exposes the internal handler in the notebook
    namespace.

    Important:
        start_agent() is a cold start. It resets the agent state, including
        cell history, execution history, symbol registry, artifact registry,
        and pending proposals.

        For temporary manual debugging, prefer pause_agent() and resume_agent().
        Those preserve the current notebook memory.

    Args:
        config:
            Optional explicit AgentConfig. If omitted, configuration is loaded
            from the default config files.
        show_welcome:
            Whether to display the notebook-native welcome panel.
        return_state:
            If True, return the initialized AgentState. Otherwise return None.

    Returns:
        AgentState if return_state=True, otherwise None.
    """
    ip = _get_ipython_shell()

    # Avoid duplicate hooks if start_agent() is called twice in the same kernel.
    old_state = get_state()
    _detach_agent_hooks(old_state, remove_handler=True)

    state = reset_state(config=config or AgentConfig.from_sources())

    transformer = build_input_transformer()
    pre_hook = build_pre_run_hook(ip)
    post_hook = build_post_run_hook(ip)

    if hasattr(ip, "input_transformers_cleanup"):
        ip.input_transformers_cleanup.insert(0, transformer)
    else:
        ip.input_transformers_post.append(transformer)

    ip.events.register("pre_run_cell", pre_hook)
    ip.events.register("post_run_cell", post_hook)
    ip.user_ns["__auto_agent_handle__"] = __auto_agent_handle__

    state.started = True
    state.paused = False
    state.hooks = {
        "transformer": transformer,
        "pre_run_cell": pre_hook,
        "post_run_cell": post_hook,
        "ip": ip,
    }

    if show_welcome:
        _show_welcome_screen(state)

    return state if return_state else None



def stop_agent(*, show_note: bool = True) -> None:
    """
    Fully stop the notebook agent and detach all registered hooks.

    This removes:
    - the natural-language input transformer,
    - the pre-run historian hook,
    - the post-run historian hook,
    - the internal __auto_agent_handle__ namespace helper.

    Unlike pause_agent(), this stops both routing and passive notebook tracking.
    The in-memory state object is not reset here, but no further cells will be
    tracked until start_agent() is called again. Calling start_agent() later will
    create a fresh state.

    Args:
        show_note:
            Whether to show a small notebook-native status message.
    """
    state = get_state()
    was_running = bool(state.started or state.hooks)

    _detach_agent_hooks(state, remove_handler=True)

    state.started = False
    state.paused = False
    state.current_cell = None
    state.hooks = {}

    if show_note:
        if was_running:
            show_message(
                f"{state.config.name} stopped",
                (
                    "All agent hooks were detached. Natural-language routing and "
                    "notebook tracking are now off. Use start_agent() for a fresh start."
                ),
            )
        else:
            show_message(
                "Agent already stopped",
                "No active agent hooks were found.",
            )

  
def pause_agent(*, show_note: bool = True) -> None:
    """
    Temporarily pause natural-language cell routing without stopping notebook tracking.

    This removes only the input transformer that converts non-Python code cells into
    agent requests. The pre/post execution hooks remain active, so normal Python cells
    still run normally and still update the agent's notebook memory.

    Use this when you want to:
    - copy/paste generated code into a normal Python cell,
    - debug it manually and see raw Python errors,
    - repair code yourself,
    - run the repaired cell so the agent can learn the resulting symbols/state,
    - optionally edit config files before calling resume_agent().

    Notes:
    - Natural-language code cells will not be intercepted while paused.
    - Python error review should usually be disabled while paused via the historian guard.
    - This does not reset execution history, symbol registry, or pending proposals.
    """
    state = get_state()
    hooks = state.hooks or {}
    ip = hooks.get("ip")

    if ip is None:
        show_message(
            "Agent not running",
            "No active agent session was found. Use start_agent() first.",
        )
        return

    transformer = hooks.get("transformer")
    for attr in ("input_transformers_cleanup", "input_transformers_post"):
        transformers = getattr(ip, attr, [])
        if transformer in transformers:
            transformers.remove(transformer)

    state.paused = True
    state.started = True

    if show_note:
        show_message(
            f"{state.config.name} paused",
            (
                "Natural-language routing is paused. Python cells still run normally "
                "and are still tracked. You can now debug manually, edit "
                "notebook_native_agent.config.json or openai.config.json, then call "
                "resume_agent() to continue."
            ),
        )


def resume_agent(
    config: Optional[AgentConfig] = None,
    *,
    reload_config: bool = True,
    provider_config_path: Optional[str] = None,
    runtime_config_path: Optional[str] = None,
    show_note: bool = True,
) -> None:
    """
    Resume natural-language cell routing without resetting notebook memory.

    By default, this reloads configuration from JSON files before re-enabling the
    input transformer. That lets the user pause, edit settings, and resume with the
    new values while preserving cell history, execution history, symbols, artifacts,
    and pending proposals.

    Args:
        config:
            Optional explicit AgentConfig object. If provided, it replaces the current
            config and JSON reload is skipped.
        reload_config:
            If True, reload AgentConfig.from_sources(...) before resuming. This is
            useful after editing notebook_native_agent.config.json or openai.config.json.
        provider_config_path:
            Optional path to openai.config.json. If omitted, the current config's
            provider_config_path is reused when available.
        runtime_config_path:
            Optional path to notebook_native_agent.config.json. If omitted, the default
            runtime config path is used.
        show_note:
            Whether to show a small notebook message after resuming.

    Notes:
    - This does not call reset_state().
    - This does not re-register historian hooks; they should already be active.
    - Config changes affect future cells. Existing history/snapshots are not rewritten.
    """
    state = get_state()
    hooks = state.hooks or {}
    ip = hooks.get("ip")

    if ip is None:
        raise RuntimeError("No active agent session found. Use start_agent() first.")

    if config is not None:
        state.config = config
    elif reload_config:
        state.config = AgentConfig.from_sources(
            provider_config_path=(
                provider_config_path
                or getattr(state.config, "provider_config_path", None)
            ),
            runtime_config_path=runtime_config_path,
        )

    transformer = hooks.get("transformer")
    if transformer is None:
        transformer = build_input_transformer()
        hooks["transformer"] = transformer
        state.hooks = hooks

    if hasattr(ip, "input_transformers_cleanup"):
        ip.input_transformers_cleanup.insert(0, transformer)
    else:
        ip.input_transformers_post.append(transformer)

    state.paused = False
    state.started = True

    if show_note:
        show_message(
            f"{state.config.name} resumed",
            (
                "Natural-language routing is active again. Configuration was "
                f"{'reloaded' if reload_config and config is None else 'kept as provided'}, "
                "and existing notebook memory was preserved."
            ),
        )

