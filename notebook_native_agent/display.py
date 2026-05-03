from __future__ import annotations

from html import escape
from typing import Iterable, Optional
from uuid import uuid4

from IPython.display import HTML, display


def _join_reasons(reasons: Optional[Iterable[str]]) -> str:
    if not reasons:
        return ""
    return "<br>".join(f"• {escape(str(reason))}" for reason in reasons)


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    return str(value)


def _render_python_code_html(code: str) -> str:
    safe_code = _to_text(code)
    try:
        from pygments import highlight  # noqa: WPS433
        from pygments.formatters import HtmlFormatter  # noqa: WPS433
        from pygments.lexers import PythonLexer  # noqa: WPS433

        formatter = HtmlFormatter(style="monokai", cssclass="auto-agent-code", nowrap=False)
        highlighted = highlight(safe_code, PythonLexer(), formatter)
        css = formatter.get_style_defs(".auto-agent-code")
        return f"<style>{css}</style>{highlighted}"
    except Exception:
        return f"<pre class='auto-agent-code-fallback'>{escape(safe_code)}</pre>"


def _render_markdown_html(text: str) -> str:
    safe_text = _to_text(text)
    try:
        import markdown  # noqa: WPS433

        return markdown.markdown(
            safe_text,
            extensions=["extra", "sane_lists", "nl2br"],
            output_format="html5",
        )
    except Exception:
        return f"<div style='white-space:pre-wrap;'>{escape(safe_text)}</div>"


def show_agent_panel(
    *,
    agent_name: str,
    understood: str,
    solution: str,
    code: str,
    execution_label: str,
    context_summary: Optional[str] = None,
    safety_reasons: Optional[Iterable[str]] = None,
    observed_error: Optional[str] = None,
) -> None:
    safe_agent_name = _to_text(agent_name)
    safe_understood = _to_text(understood)
    safe_solution = _to_text(solution)
    safe_code = _to_text(code)
    safe_execution_label = _to_text(execution_label)
    safe_context_summary = _to_text(context_summary)
    safe_observed_error = _to_text(observed_error)
    try:
        from IPython.display import HTML, display  # noqa: WPS433
    except Exception:
        print(agent_name)
        print("What I understood")
        print(understood)
        if safe_observed_error:
            print("\nObserved error")
            print(safe_observed_error)
        print("\nProposed solution")
        print(solution)
        print("\nCode preview")
        print(code)
        print("\nExecution")
        print(execution_label)
        return

    panel_id = f"auto-agent-{uuid4().hex}"
    code_block_id = f"{panel_id}-code"
    copy_btn_id = f"{panel_id}-copy"
    context_block_id = f"{panel_id}-context"
    code_html = _render_python_code_html(safe_code)
    solution_html = _render_markdown_html(safe_solution)

    context_html = ""
    if safe_context_summary:
        rendered_context = _render_markdown_html(safe_context_summary)
        context_html = f"""
        <div style='margin-top:12px;'>
          <div style='font-weight:700;margin-bottom:6px;'>Selected context</div>
          <div id='{context_block_id}' class='auto-agent-markdown' style='background:#f7f7f8;border:1px solid #ddd;padding:10px;border-radius:10px;color:#111827;'>
            {rendered_context}
          </div>
        </div>
        """

    reasons_html = ""
    if safety_reasons:
        reasons_html = f"""
        <div style='margin-top:12px;'>
          <div style='font-weight:700;margin-bottom:6px;'>Safety notes</div>
          <div style='background:#fff8e1;border:1px solid #f3d98c;padding:10px;border-radius:10px;color:#111827;'>{_join_reasons(safety_reasons)}</div>
        </div>
        """

    observed_error_html = ""
    if safe_observed_error:
        observed_error_html = f"""
        <div style='margin-bottom:12px;'>
          <div style='font-weight:700;margin-bottom:6px;'>Observed error</div>
          <div style='white-space:pre-wrap;background:#fff1f2;border:1px solid #fda4af;padding:10px;border-radius:10px;color:#881337;'>{escape(safe_observed_error)}</div>
        </div>
        """

    html = f"""
    <div id='{panel_id}' style='font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;border:1px solid #ddd;border-radius:16px;padding:16px;background:white;box-shadow:0 1px 2px rgba(0,0,0,0.04);'>
      <style>
        #{panel_id} .auto-agent-code-wrap {{
          position: relative;
          margin-bottom: 12px;
          background: #0b1020;
          border: 1px solid #1f2937;
          border-radius: 12px;
          overflow: hidden;
        }}
        #{panel_id} .auto-agent-code-toolbar {{
          display: flex;
          justify-content: flex-end;
          align-items: center;
          padding: 8px 10px;
          background: #111827;
          border-bottom: 1px solid #1f2937;
        }}
        #{panel_id} .auto-agent-copy-btn {{
          border: 1px solid #374151;
          background: #111827;
          color: #e5e7eb;
          border-radius: 8px;
          padding: 4px 9px;
          font-size: 13px;
          cursor: pointer;
          line-height: 1.2;
        }}
        #{panel_id} .auto-agent-copy-btn:hover {{
          background: #1f2937;
        }}
        #{panel_id} .auto-agent-code {{
          margin: 0;
          padding: 14px 16px;
          overflow-x: auto;
          background: #0b1020;
        }}
        #{panel_id} .auto-agent-code pre {{
          margin: 0;
          white-space: pre-wrap;
          word-break: break-word;
          font-size: 13px;
          line-height: 1.5;
          background: transparent;
        }}
        #{panel_id} .auto-agent-code-fallback {{
          margin: 0;
          padding: 14px 16px;
          white-space: pre-wrap;
          word-break: break-word;
          background: #0b1020;
          color: #e5e7eb;
          font-size: 13px;
          line-height: 1.5;
        }}
        #{panel_id} #{context_block_id} p:first-child {{
          margin-top: 0;
        }}
        #{panel_id} #{context_block_id} p:last-child {{
          margin-bottom: 0;
        }}
        #{panel_id} #{context_block_id} ul,
        #{panel_id} #{context_block_id} ol {{
          margin: 0.35rem 0 0.35rem 1.2rem;
          padding-left: 1rem;
        }}
        #{panel_id} #{context_block_id} code {{
          background: #e5e7eb;
          border-radius: 4px;
          padding: 0 4px;
          font-size: 0.95em;
        }}
        #{panel_id} .auto-agent-markdown p:first-child {{
          margin-top: 0;
        }}
        #{panel_id} .auto-agent-markdown p:last-child {{
          margin-bottom: 0;
        }}
        #{panel_id} .auto-agent-markdown ul,
        #{panel_id} .auto-agent-markdown ol {{
          margin: 0.35rem 0 0.35rem 1.2rem;
          padding-left: 1rem;
        }}
        #{panel_id} .auto-agent-markdown code {{  
          background: #e5e7eb;
          border-radius: 4px;
          padding: 0 4px;
          font-size: 0.95em;
        }}        
      </style>
      <div style='font-size:20px;font-weight:800;margin-bottom:12px;color:#111827;'>{escape(safe_agent_name)}</div>
      <div style='font-weight:700;margin-bottom:6px;color:#111827;'>What I understood</div>
      <div style='margin-bottom:12px;color:#111827;'>{escape(safe_understood)}</div>
      {observed_error_html}
      <div style='font-weight:700;margin-bottom:6px;color:#111827;'>Proposed solution</div>
      <div class='auto-agent-markdown auto-agent-solution' style='margin-bottom:12px;color:#111827;'>
        {solution_html}
      </div>
      <div style='font-weight:700;margin-bottom:6px;color:#111827;'>Code preview</div>
      <div class='auto-agent-code-wrap'>
        <div class='auto-agent-code-toolbar'>
          <button id='{copy_btn_id}' class='auto-agent-copy-btn' type='button'>⧉ copy</button>
        </div>
        <div id='{code_block_id}'>{code_html}</div>
      </div>
      <script>
        (function() {{
          const btn = document.getElementById('{copy_btn_id}');
          const codeEl = document.getElementById('{code_block_id}');
          const panelEl = document.getElementById('{panel_id}');

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

          if (btn && codeEl) {{
            btn.addEventListener('click', async function() {{
              const text = codeEl.innerText || codeEl.textContent || '';
              const old = btn.innerText;

              const ok = await copyText(text);
              btn.innerText = ok ? '✓ copied' : 'copy failed';
              setTimeout(() => btn.innerText = old, 1200);
            }});
          }}

          if (window.MathJax && typeof window.MathJax.typesetPromise === 'function' && panelEl) {{
            window.MathJax.typesetPromise([panelEl]).catch(function() {{}});
          }}
        }})();
      </script>
      <div style='font-weight:700;margin-bottom:6px;color:#111827;'>Execution</div>
      <div style='color:#111827;'>{escape(safe_execution_label)}</div>
      {context_html}
      {reasons_html}
    </div>
    """
    display(HTML(html))


def show_message(title: str, body: str) -> None:
    try:
        from IPython.display import HTML, display  # noqa: WPS433
        html = f"""
        <div style='font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin-top:10px;border-left:4px solid #5b7cfa;padding:10px 12px;background:#f6f8ff;'>
          <div style='font-weight:700;color:#111827;'>{escape(title)}</div>
          <div style='color:#111827;'>{escape(body)}</div>
        </div>
        """
        display(HTML(html))
    except Exception:
        print(f"{title}: {body}")
