# Notebook Native Agent

> Turn Jupyter into a notebook-native coding workspace with **natural-language cells, live context awareness, safe auto-execution, memory, provenance, and receipts**.

---

## What it is

**Notebook Native Agent** is a Python package that plugs directly into a live Jupyter/IPython runtime.

Inside the same notebook, you can write either:

- normal Python cells, or
- natural-language request cells.

The agent observes the live notebook state, reuses existing imports, variables, objects, functions, classes, and prior executions, proposes code directly in notebook output, auto-runs only eligible code, and keeps track of what was proposed, what actually ran, what changed, and what failed.

This is not “chat next to a notebook.”

It is an attempt to make the **notebook itself** feel agentic.

---

## Why it feels different

Typical copilots often have weak grounding in the actual live notebook state. They may miss:

- which imports already exist,
- which variables, functions, classes, and instantiated objects are available,
- which code was only suggested,
- which code actually executed,
- what changed in the namespace,
- what failed and why,
- and which previous helpers are worth reusing.

Notebook Native Agent is built around those gaps.

It combines:

- **cell interception**
- **live namespace awareness**
- **context selection and summarization**
- **notebook-aware code generation**
- **structured notebook-native output**
- **safe auto-execution**
- **execution history**
- **symbol provenance**
- **lightweight function/class introspection**
- **bounded self-repair**
- **review-only suggestions for failed user code**
- **pause/resume controls for manual debugging**

---

## Quick example

Write a notebook cell like this:

```text
Show me the revenue trend by month
```

The router can transform it internally into:

```python
__auto_agent_handle__("Show me the revenue trend by month")
```

Then the agent can:

1. inspect the current notebook context,
2. identify relevant dataframes or reusable helpers,
3. generate Python grounded in what already exists,
4. show a structured code preview in notebook output,
5. auto-execute only if the code passes the safety gate.

---

## Core capabilities

### 1. Natural-language cells

Write natural-language requests directly inside notebook code cells. The router turns non-Python text into agent requests.

### 2. Live notebook context

The agent tracks notebook symbols, reusable helpers, object summaries, prior executions, and provenance.

For functions and classes, it can retain lightweight metadata such as signatures, docstrings, public member names, and callable signatures.

### 3. Structured notebook-native output

Generated responses are shown inside notebook output with sections such as:

- **What I understood**
- **Observed error**
- **Proposed solution**
- **Code preview**
- **Execution**
- **Selected context**
- **Safety notes**

The code preview includes a copy button, with a fallback path for notebook environments that restrict the Clipboard API.

### 4. Safe auto-execution

Only code that passes the rules-first safety gate is eligible for auto-run.

### 5. Transparent memory and provenance

The agent tracks:

- `cell_history`
- `exec_history`
- `symbol_registry`
- `artifact_registry`
- `pending_proposals`

It also distinguishes provenance values such as:

- `user_created`
- `user_imported`
- `agent_auto_executed`
- `agent_proposed_then_user_executed`

### 6. One bounded repair retry

If safe auto-executed agent code fails once, the agent can generate one repaired version, re-check safety, and retry once.

### 7. Conservative Python error review

If a normal user Python cell fails, the agent does **not** silently rerun corrected code.

Instead, it can show the original error, explain the likely issue, and propose a corrected version as **preview only**.

### 8. Pause and resume

Use `pause_agent()` when you want to debug manually without losing notebook memory.

While paused:

- natural-language routing is paused,
- Python cells still run normally,
- historian hooks still track executed Python cells,
- Python error review is skipped,
- generated/fixed code can still update the symbol registry.

Use `resume_agent()` to re-enable natural-language routing. By default, it reloads `notebook_native_agent.config.json` and `openai.config.json`, so you can pause, edit config, and continue without resetting notebook memory.

---

## How it works

The runtime is intentionally split into a few clear roles:

- **router** — decides whether a cell is Python or natural language, then rewrites natural-language requests.
- **handler / brain** — selects context, interprets requests, generates code, decides preview vs auto-run, handles repair, and handles Python error review.
- **historian** — records what happened before and after execution, updates symbol provenance, and tracks artifacts.

This keeps the design inspectable and easier to evolve.

---

## Project structure

Recommended repo / Kaggle demo bundle structure:

```text
notebook-native-agent-demo/
├── README.md
├── PROJECT_DESCRIPTION.md
├── requirements.txt
├── kaggle_sample.ipynb
├── notebook_native_agent.config.json
├── openai.config.json
├── notebook_native_agent/
│   ├── __init__.py
│   ├── config_env.py
│   ├── start.py
│   ├── router.py
│   ├── handler.py
│   ├── historian.py
│   ├── display.py
│   ├── registry.py
│   ├── safety.py
│   ├── utils.py
│   └── agent_inspectors.py
├── data/
│   └── tips.csv
├── notebook_samples/
│   ├── 01_sample_tips.ipynb
│   └── 02_sinx_cosy.ipynb
│ ...
└── sample_exports/
    ├── html/
    │   ├── 01_sample_tips.html
    │   └── 02_sinx_cosy.html
    │   ...
    └── pdf/
        ├── 01_sample_tips.pdf
        └── 02_sinx_cosy.pdf.pdf
```

### Module responsibilities

- `start.py` — startup, stop, pause/resume, hook registration, welcome screen rendering.
- `router.py` — cell classification and natural-language-to-handler transformation.
- `handler.py` — context selection, request interpretation, code generation, auto-exec decisions, repair retry, Python error review.
- `historian.py` — pre/post execution tracking, namespace diffing, provenance, proposal acceptance, artifact logging.
- `display.py` — notebook-native UI panels, markdown/code rendering, copy-enabled code preview.
- `registry.py` — runtime config, role config resolution, state containers, execution registries.
- `safety.py` — rules-first execution classification.
- `utils.py` — provider calls, code normalization, JSON coercion, namespace snapshots, symbol metadata helpers.
- `agent_inspectors.py` — user-facing inspection helpers.

---

## Configuration

The project uses two root-level JSON config files plus optional local secrets.

### `.env`

For local development only:

```dotenv
OPENAI_API_KEY=your_key_here
```

Do **not** put `.env` in a public repo or Kaggle Dataset.

### `openai.config.json`

Role-specific OpenAI settings:

```json
{
  "classifier": {
    "model": "gpt-5.4-nano",
    "reasoning_effort": "low",
    "verbosity": "low"
  },
  "interpreter": {
    "model": "gpt-5.4-mini",
    "reasoning_effort": "medium",
    "verbosity": "low"
  },
  "summarizer": {
    "model": "gpt-5.4-mini",
    "reasoning_effort": "medium",
    "verbosity": "low"
  },
  "brain": {
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
    "verbosity": "medium"
  },
  "repair": {
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
    "verbosity": "low"
  },
  "python_error_review": {
    "model": "gpt-5.4-mini",
    "reasoning_effort": "medium",
    "verbosity": "low"
  }
}
```

### `notebook_native_agent.config.json`

Runtime behavior:

```json
{
  "name": "Notebook Native Agent",
  "auto_execute": true,
  "allow_fallback_codegen": true,
  "use_model_classifier": false,
  "echo_context": true,
  "max_context_items": 10,
  "max_repr_chars": 200,
  "allow_repair_retry": true,
  "max_auto_repair_attempts": 1,
  "raise_on_auto_exec_failure": false,
  "max_error_chars": 1600,
  "assist_on_python_error": true
}
```

Important behavior:

- If `allow_fallback_codegen` is `false` and no brain model/API key is available, the agent returns a strict scaffold instead of hidden hardcoded behavior.
- If `allow_fallback_codegen` is `true` and no brain model/API key is available, the agent uses one fixed safe demo fallback: a simple `np.sin(x)` plot. This is intentionally not presented as a real model-generated answer.

---

## Local quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add your API key

Create `.env` in the repo root:

```dotenv
OPENAI_API_KEY=your_key_here
```

### 3. Start the agent in a notebook

```python
from notebook_native_agent import (
    start_agent,
    stop_agent,
    pause_agent,
    resume_agent,
    agent_status,
    agent_symbols,
)

start_agent()
```

### 4. Try natural-language cells

```text
Plot a sine wave from 0 to 2π
```

```text
Show me the revenue trend by month
```

```text
Show me how to normalize this dataframe, but don't run it
```

---

## Kaggle demo flow

For a public Kaggle demo, use `kaggle_sample.ipynb` as the entry notebook.

Recommended notebook flow:

1. Markdown intro.
2. Copy the attached Kaggle Dataset bundle from `/kaggle/input/...` to `/kaggle/working/...`.
3. Optionally edit `notebook_native_agent.config.json` and `openai.config.json` in a collapsed config cell.
4. Load `OPENAI_API_KEY` from Kaggle Secrets.
5. Import and start the agent.

Example startup cell:

```python
import os
import sys
import shutil
from pathlib import Path

candidates = [
    p for p in Path("/kaggle/input").rglob("notebook_native_agent")
    if p.is_dir()
]

if not candidates:
    raise FileNotFoundError("Could not find notebook_native_agent package under /kaggle/input.")

PACKAGE_SRC = candidates[0]
SRC = PACKAGE_SRC.parent
DST = Path("/kaggle/working/notebook-native-agent-demo")

if DST.exists():
    shutil.rmtree(DST)

shutil.copytree(SRC, DST)

sys.path.insert(0, str(DST))
os.chdir(DST)

print("Project copied to:", DST)
print("Current working directory:", Path.cwd())
```

Load the Kaggle secret:

```python
import os
from kaggle_secrets import UserSecretsClient

user_secrets = UserSecretsClient()
os.environ["OPENAI_API_KEY"] = user_secrets.get_secret("OPENAI_API_KEY")

print("OPENAI_API_KEY loaded from Kaggle Secrets.")
```

Start the agent:

```python
from notebook_native_agent import start_agent, stop_agent, pause_agent, resume_agent, agent_status, agent_symbols

start_agent()
```

---

## Lifecycle helpers

### `start_agent()`

Cold-starts the agent, registers hooks, resets state, and shows the welcome panel.

Use this at the beginning of a notebook session.

### `pause_agent()`

Temporarily disables natural-language routing but keeps passive notebook tracking active.

Useful when you want to manually debug generated code, inspect raw errors, edit config files, or run repaired code while preserving agent memory.

### `resume_agent()`

Re-enables natural-language routing without resetting notebook memory.

By default, it reloads the JSON config files before resuming.

### `stop_agent()`

Fully detaches all hooks. Natural-language routing and passive tracking both stop.

Calling `start_agent()` later creates a fresh state.

---

## Introspection helpers

```python
agent_status()
agent_symbols()
```

`agent_status()` shows a compact runtime snapshot: started/paused state, provider, model roles, runtime flags, current cell, and counts for cells, executions, symbols, artifacts, and proposals.

`agent_symbols()` shows the current symbol registry, including type, symbol kind, signature, docstring, public members, callable signatures, provenance, last seen cell, deleted flag, and repr.

---

## Safety posture

This project uses a **rules-first** safety gate.

Typical manual-review triggers include:

- shell commands,
- package installation,
- filesystem writes,
- network access,
- destructive operations,
- ambiguous or expensive side effects.

Typical safe auto-run cases include:

- in-memory inspection,
- plotting,
- dataframe summaries,
- simple transformations,
- helper definitions.

Safety is checked again before any repair retry.

---

## Example demo scenarios

### Housing price regression

A strong context-awareness demo using `Housing.csv`:

```text
Load Housing.csv into a dataframe called df, inspect its structure, missing values, dtypes, and summarize the prediction objective.
```

```text
Based on df and the objective, propose a step-by-step regression plan for single-feature and multiple-feature regression, including categorical encoding and multicollinearity checks. Do not train models yet.
```

```text
Build a simple linear regression model using area only to predict price. Evaluate it with R2, RMSE, and MAE.
```

```text
Build Ridge and Lasso models to address multicollinearity, evaluate them, and add their scores to the comparison table.
```

### Reusing a custom class

```python
class DataFrameAggregator:
    """Reusable dataframe aggregation helper."""
    def __init__(self, df):
        self.df = df

    def sum_by_group(self, group_col, value_col):
        return self.df.groupby(group_col)[value_col].sum()
```

Then ask:

```text
Instantiate this aggregator with my dataframe and use it to sum revenue by region.
```

The agent should detect the class, its constructor, its public method, and the existing dataframe.

### Manual debug with pause/resume

```python
pause_agent()
```

Manually run/fix generated code and inspect raw Python errors.

```python
resume_agent()
agent_symbols()
```

The agent continues with the repaired notebook state preserved.

---

## Current scope

This repo is a focused PoC for:

- Jupyter/IPython integration,
- OpenAI-only provider path,
- JSON-based role and runtime config,
- live notebook context awareness,
- transparent state, history, and provenance,
- safe auto-exec with bounded repair,
- inspectable memory and symbol reuse.

It is intentionally not a generic multi-agent framework.

---

## View demos without running Python

The optional `sample_exports/` folder can contain exported HTML and PDF versions of selected demo notebooks, so visitors can inspect results without launching a heavy Python environment.

Suggested layout:

```text
sample_exports/
├── html/
└── pdf/
```

---

## One-line summary

**Natural-language Jupyter, with live context, memory, provenance, safety, symbol introspection, and receipts.**
