# Notebook Native Agent — Project Description

## One-line description

Notebook Native Agent is a notebook-native coding assistant for Jupyter/IPython that lets users write normal Python or natural-language requests directly in notebook cells, generates notebook-aware Python grounded in the live runtime, safely auto-executes eligible code, and keeps explicit memory of proposals, executions, symbol changes, artifacts, failures, and provenance.

---

## Vision

Turn a notebook into a **stateful coding workspace** where the assistant is not an external chat panel, but part of the notebook runtime itself.

The user can:

- write normal Python cells,
- write natural-language request cells,
- receive structured assistant output directly in notebook output,
- preview generated code before execution,
- allow safe auto-execution when appropriate,
- pause and resume agent routing while preserving notebook memory,
- inspect what the agent currently knows,
- and benefit from execution memory grounded in the real notebook state.

The goal is not “chat next to a notebook.” It is a notebook collaborator with **context, memory, provenance, safety, and receipts**.

---

## Why this project matters

Typical coding copilots often have weak grounding in the actual live notebook state. They may not reliably know:

- which imports already exist,
- which variables, functions, classes, and instantiated objects are available,
- which code was only proposed,
- which code actually executed,
- what changed in the namespace,
- which generated snippets failed,
- which user Python cells failed,
- and which previous helpers are worth reusing.

Notebook Native Agent addresses that by combining:

- cell interception,
- live namespace awareness,
- role-based LLM calls,
- context selection and summarization,
- explicit execution history,
- symbol provenance,
- lightweight function/class introspection,
- artifact tracking,
- rules-first safety checks,
- bounded self-repair,
- conservative Python error review,
- pause/resume controls,
- and user-facing inspection helpers.

---

## Core design principle

The architecture is intentionally separated into three runtime roles:

- **router** — decides whether a cell is normal Python or a natural-language agent request.
- **handler / brain** — interprets requests, selects context, generates code, decides preview vs auto-exec, and handles repair/error review.
- **historian** — records what actually happened before and after cell execution.

This keeps the system understandable, debuggable, and easy to evolve.

---

## What the system does

### 1. Observes every cell

The assistant watches all notebook cells, not only natural-language requests.

That allows it to track:

- user imports,
- user-created variables,
- modified symbols,
- deleted symbols,
- generated matplotlib figures,
- accepted assistant proposals,
- and the relationship between notebook state and assistant actions.

### 2. Accepts natural-language cells

A user can write a cell like:

```text
Show me the revenue trend by month
```

The router can transform it into an internal handler call:

```python
__auto_agent_handle__("Show me the revenue trend by month")
```

The router is designed to be lightweight. It uses Python syntax classification first, with an optional model-based classifier when enabled.

### 3. Shows notebook-native structured output

Assistant responses are displayed directly in notebook output as structured HTML panels with sections such as:

- **What I understood**
- **Observed error**
- **Proposed solution**
- **Code preview**
- **Execution**
- **Selected context**
- **Safety notes**

The code preview is visually distinct and includes a copy button. The copy behavior includes a fallback path for restricted environments such as Kaggle if the browser Clipboard API is blocked.

### 4. Keeps generated code explicit

Generated code is stored directly in execution history instead of being reconstructed later.

That makes follow-ups more reliable for:

- “show me the last snippet,”
- iterative changes,
- provenance tracking,
- debugging,
- repair attempts,
- and proposal acceptance detection.

### 5. Distinguishes execution modes

Generated code falls into two broad paths:

- **safe auto-execute**
- **manual review / preview only**

Auto-execution is allowed only when both the model plan and the rules-first safety classifier permit it.

### 6. Performs one bounded repair retry

If assistant-generated code is auto-executed and fails, the system can:

1. record the failed attempt,
2. build a repair prompt from the request, generated code, error type, error message, and traceback excerpt,
3. generate a corrected version,
4. re-check safety,
5. retry exactly once,
6. record the final outcome.

If the repair also fails, the system stops and keeps the final error in execution history.

### 7. Reviews failed user Python cells conservatively

If a normal user Python cell fails, the system does **not** silently rerun corrected code.

Instead, it can:

- keep the original notebook error visible,
- explain the likely issue,
- propose a corrected version as **preview only**,
- and store the proposed fix as a pending proposal for manual user execution.

This preserves user control and avoids replaying side effects.

### 8. Supports pause/resume workflow

The package exposes:

```python
pause_agent()
resume_agent()
```

`pause_agent()` temporarily disables natural-language routing while keeping passive notebook tracking active. This lets the user copy generated code into a normal Python cell, debug it manually, see raw Python errors, repair it, and run the repaired version so the historian can learn the resulting symbols/state.

`resume_agent()` re-enables natural-language routing without resetting notebook memory. By default, it reloads configuration from JSON files, so the user can pause, edit `notebook_native_agent.config.json` or `openai.config.json`, and resume with new settings while preserving history.

---

## Runtime lifecycle

### `start_agent()`

Cold-starts the agent. It:

- creates a fresh `AgentState`,
- registers the input transformer,
- registers pre/post execution hooks,
- exposes `__auto_agent_handle__` in the notebook namespace,
- displays the welcome screen unless disabled.

Because `start_agent()` resets state, it is best used for a fresh session.

### `pause_agent()`

Temporarily pauses natural-language routing only. It:

- removes the input transformer,
- keeps pre/post historian hooks active,
- keeps symbol tracking active,
- preserves cell history, execution history, symbol registry, artifact registry, and pending proposals.

This is the preferred mode for manual debugging.

### `resume_agent()`

Resumes natural-language routing without resetting notebook memory. It:

- optionally reloads configuration from JSON files,
- re-adds the input transformer,
- preserves previous notebook memory,
- continues from the existing state.

### `stop_agent()`

Fully stops the agent. It:

- removes the input transformer,
- unregisters pre/post historian hooks,
- removes the internal handler from the notebook namespace,
- turns off both routing and passive tracking.

A later `start_agent()` creates a fresh state.

---

## Current architecture

### Layer 1 — Cell interception

The runtime hooks into Jupyter/IPython to observe and optionally rewrite cells.

Two responsibilities are kept separate:

- **observation** of all cells,
- **rewriting** only when a cell is classified as an assistant request.

Observation is used for:

- cell history,
- namespace snapshots,
- namespace diffs,
- provenance tracking,
- artifact tracking,
- proposal acceptance detection.

Rewriting is used for:

- routing natural-language requests into the assistant handler.

The input transformer is inserted early when `input_transformers_cleanup` is available. This improves handling of natural-language questions ending with `?` while preserving normal IPython object introspection such as `df?` and `my_function??`.

---

### Layer 2 — Router

The router decides whether a cell is:

- normal Python,
- or a natural-language assistant request.

It uses:

- syntax-based classification first,
- explicit preservation of IPython magics/shell/introspection syntax,
- and optionally a model-based classifier when enabled.

The router should stay small and predictable. Heavy reasoning belongs in the handler/brain.

---

### Layer 3 — Handler / brain

The handler is the runtime brain.

It is responsible for:

- selecting relevant notebook context,
- summarizing that context,
- interpreting the request,
- generating code,
- showing structured output,
- deciding preview vs auto-exec,
- storing execution history,
- retrying once on safe auto-run failure,
- and generating manual correction proposals for failed user Python cells.

Conceptually:

```python
def __auto_agent_handle__(user_text: str):
    # 1. select relevant context
    # 2. summarize context
    # 3. interpret request
    # 4. generate code plan
    # 5. safety-check code
    # 6. preview or execute
    # 7. optionally repair once if auto-run failed
    # 8. record history and provenance
```

### Brain prompt design

The brain prompt emphasizes notebook-specific behavior:

- reuse existing notebook symbols whenever possible,
- avoid inventing unavailable symbols,
- keep simple tasks simple,
- create small reusable helpers when useful,
- prefer functions over classes unless stateful structure is natural,
- use clear names,
- add concise type hints when practical,
- add short docstrings for reusable helpers,
- explicitly render visible results with `display(...)` or `print(...)`,
- for matplotlib, create and render figures explicitly,
- for Plotly, call `fig.show()`,
- print a short confirmation for silent helper/class definitions,
- and set preview-only mode when the user says not to run.

---

### Layer 4 — Historian

The historian records what actually happened around execution.

It tracks:

- raw cell text,
- transformed cell text,
- cell kind,
- execution status,
- created / modified / deleted symbols,
- accepted proposals,
- linked assistant executions,
- produced artifacts,
- and timestamps.

It is the system’s factual memory of notebook activity.

When symbols are created or modified, the historian enriches symbol entries with lightweight metadata extracted from the live object when possible.

---

## Provenance model

The assistant keeps explicit provenance for symbols and executions.

Representative provenance values include:

- `user_created`
- `user_imported`
- `agent_auto_executed`
- `agent_proposed_then_user_executed`

This distinction matters because the assistant should reason differently about:

- code it only proposed,
- code it executed itself,
- code imported or created by the user,
- and code the user explicitly accepted and ran.

---

## Execution history model

The system keeps explicit registries:

- `cell_history`
- `exec_history`
- `symbol_registry`
- `artifact_registry`
- `pending_proposals`

Execution records support:

- generated code,
- selected context,
- safety reasons,
- execution mode,
- multiple attempts inside the same execution record,
- repair count,
- model used,
- fallback status,
- error type,
- error message,
- traceback excerpt,
- artifact count,
- and finish status.

This makes debugging and follow-up reasoning much more robust.

---

## Lightweight symbol intelligence

The symbol registry retains small but high-value metadata for reusable symbols.

For functions, it can store:

- `kind`
- `signature`
- `docstring`

For classes, it can also store:

- `public_member_names`
- `public_callable_signatures`

This gives the assistant more than a memory that “a class exists.” It can often infer:

- which method is available,
- how it should be called,
- and which reusable helper is most relevant to a follow-up request.

This improves prompts such as:

- “use the function we created earlier,”
- “instantiate the class and call its method,”
- “reuse that analyzer,”
- “call the aggregation helper from before.”

---

## Context selection and summaries

Before generating code, the handler selects relevant notebook context.

Ranking can use signals such as:

- symbol names,
- type information,
- signatures,
- docstrings,
- public class members,
- callable member signatures,
- repr/object summaries,
- execution history,
- and recency.

The selected context is summarized and passed into generation. This helps the model produce direct, grounded code instead of generic defensive guesses.

---

## Model architecture

Notebook Native Agent uses specialized logical roles, not a theatrical multi-agent framework.

Current roles include:

- **classifier**
- **interpreter**
- **summarizer**
- **brain**
- **repair**
- **python_error_review**

These roles may use different models and inference settings.

Representative defaults:

- `classifier` → `gpt-5.4-nano`
- `interpreter` → `gpt-5.4-mini`
- `summarizer` → `gpt-5.4-mini`
- `brain` → `gpt-5.4`
- `repair` → `gpt-5.4`
- `python_error_review` → `gpt-5.4-mini`

---

## Configuration approach

Configuration is split into two root-level JSON files plus optional local secrets.

### `.env`

Used for local secrets:

```dotenv
OPENAI_API_KEY=...
```

On Kaggle, the API key can be loaded from Kaggle Secrets and copied into `os.environ["OPENAI_API_KEY"]` before `start_agent()`.

### `openai.config.json`

Role-specific provider settings:

- model,
- enabled,
- reasoning effort,
- verbosity,
- optional request settings.

### `notebook_native_agent.config.json`

Runtime behavior:

- `name`
- `auto_execute`
- `allow_fallback_codegen`
- `use_model_classifier`
- `echo_context`
- `max_context_items`
- `max_repr_chars`
- `allow_repair_retry`
- `max_auto_repair_attempts`
- `raise_on_auto_exec_failure`
- `max_error_chars`
- `assist_on_python_error`

`resume_agent()` reloads configuration by default, so users can pause, edit JSON config files, and resume without losing notebook memory.

---

## Demo fallback behavior

When no brain model/API key is available and fallback mode is enabled, the assistant does **not** pretend that a real model-generated answer exists.

Instead, it returns one fixed safe example: a simple `np.sin(x)` plot.

This keeps demos honest:

- real model unavailable,
- fallback enabled,
- one safe fixed example returned,
- no fake reasoning or fake request-specific answer.

---

## Safety policy

The assistant uses a rules-first execution classifier.

Typical safe auto-exec cases:

- plotting,
- dataframe inspection,
- harmless in-memory transformations,
- helper definitions,
- simple analytics.

Typical manual-only cases:

- shell commands,
- package installation,
- filesystem writes,
- network access,
- destructive operations,
- ambiguous expensive operations.

Safety is checked before auto-execution and checked again before any repair retry.

---

## Agent self-inspection helpers

The package exposes lightweight notebook helpers:

```python
from notebook_native_agent import (
    start_agent,
    pause_agent,
    resume_agent,
    stop_agent,
    agent_status,
    agent_symbols,
)

start_agent()
```

### `agent_status()`

Shows a compact snapshot of runtime state, including:

- whether the agent is started,
- whether it is paused,
- provider,
- key runtime flags,
- role models,
- current cell,
- counts for cells, executions, symbols, artifacts, and pending proposals.

### `agent_symbols()`

Shows the current symbol registry view, including for each active symbol:

- type,
- symbol kind,
- signature,
- docstring,
- public member names,
- public callable signatures,
- provenance,
- last seen cell,
- deleted flag,
- repr/object summary.

These helpers make the agent’s memory transparent and easier to trust.

---

## Current module structure

```text
notebook_native_agent/
├── __init__.py
├── config_env.py
├── start.py
├── router.py
├── handler.py
├── historian.py
├── display.py
├── registry.py
├── safety.py
├── utils.py
└── agent_inspectors.py
```

### Responsibilities

- `__init__.py`
  - public package exports
  - `start_agent`, `pause_agent`, `resume_agent`, `stop_agent`, `agent_status`, `agent_symbols`

- `config_env.py`
  - optional `.env` loading for local development

- `start.py`
  - startup and hook registration
  - hook detachment
  - welcome screen rendering
  - `pause_agent()` / `resume_agent()` lifecycle helpers
  - `stop_agent()` full shutdown

- `router.py`
  - cell classification
  - preservation of normal IPython syntax
  - natural-language-to-handler transformation

- `handler.py`
  - request interpretation
  - context selection and summarization
  - code generation
  - auto-exec decisioning
  - bounded repair retry
  - Python error review
  - strict scaffold and demo fallback behavior

- `historian.py`
  - pre/post execution hooks
  - namespace diffing
  - cell logging
  - proposal acceptance detection
  - provenance updates
  - lightweight symbol enrichment
  - artifact tracking

- `display.py`
  - notebook-native UI panels
  - markdown rendering
  - syntax-highlighted code preview
  - copy button support
  - compact status messages

- `registry.py`
  - runtime config
  - role config resolution
  - state containers
  - execution registries
  - global state reset/access

- `safety.py`
  - rules-first execution classification

- `utils.py`
  - provider calls
  - code normalization
  - JSON coercion
  - namespace snapshots
  - symbol introspection helpers
  - IPython syntax classification

- `agent_inspectors.py`
  - `agent_status()`
  - `agent_symbols()`

---

## Suggested repository / Kaggle demo structure

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

The Kaggle sample notebook can act as the main entry point:

1. short Markdown introduction,
2. setup cell that copies the package/config/data from `/kaggle/input` to `/kaggle/working`,
3. optional collapsed config override cell,
4. Kaggle Secrets cell for `OPENAI_API_KEY`,
5. `start_agent()` cell,
6. demo cells using natural-language requests.

---

## Example scenarios

### Scenario 1 — Housing price regression workflow

The user has `Housing.csv` and wants to understand the dataset, clean it, build single-feature and multi-feature regression models, evaluate R²/RMSE/MAE, and address multicollinearity.

A good natural-language sequence:

```text
Load Housing.csv into a dataframe called df, inspect its structure, missing values, dtypes, and summarize the prediction objective.
```

```text
Based on df and the objective, propose a clear step-by-step modeling plan for single-feature and multiple-feature regression, including categorical encoding and multicollinearity checks. Do not train models yet.
```

```text
Create a cleaned/preprocessed dataframe for regression. Encode categorical columns, keep price as the target, and explain the transformations.
```

```text
Build a simple linear regression model using area only to predict price. Evaluate it with R2, RMSE, and MAE.
```

```text
Build a multiple linear regression model using all suitable features. Use the same train/test split and compare its metrics with the area-only model.
```

```text
Analyze multicollinearity using correlation and VIF. Show which features may be problematic.
```

```text
Build Ridge and Lasso models to address multicollinearity, evaluate them, and add their scores to the comparison table.
```

This scenario highlights live context reuse: `df`, preprocessed features, target column, train/test split, models, metrics table, and VIF results can all become part of notebook memory.

### Scenario 2 — Reuse a remembered function

User creates or asks the agent to create a reusable helper.

Later:

```text
Use the function we created earlier on df and show the result.
```

The assistant should retrieve the earlier function from symbol memory, reuse `df`, call the remembered helper directly, and display the result.

### Scenario 3 — Reuse a remembered class method

User creates or asks the agent to create a class such as `DataFrameAggregator`.

Later:

```text
Instantiate the class with df and call its sum_by_group method for revenue by region.
```

The assistant should find the class, use stored class metadata, inspect public callable signatures, generate a direct method call with the correct argument order, and display the result.

### Scenario 4 — Manual debug with pause/resume

The agent proposes code that fails or needs manual refinement.

The user can run:

```python
pause_agent()
```

Then copy/paste the generated code into a normal Python cell, debug manually, and execute the repaired code.

After that:

```python
resume_agent()
agent_symbols()
```

The agent resumes natural-language routing while preserving the repaired notebook state as context.

### Scenario 5 — Failed user Python cell review

User runs a Python cell that fails.

The notebook still shows the original error. The assistant can add a review panel with:

- likely intent,
- short diagnosis,
- corrected code preview,
- preview-only execution label,
- stored proposal for manual rerun.

---

## User experience principles

### 1. Be explicit

Always show generated code.

### 2. Be grounded

Reuse existing notebook symbols whenever possible.

### 3. Be conservative with execution

Auto-execute only code that passes the safety policy.

### 4. Preserve user control

Failed user Python cells should produce review-only suggestions, not silent reruns.

### 5. Keep memory transparent

Log proposals, executions, retries, failures, accepted proposals, symbol changes, and provenance.

### 6. Make the agent inspectable

Users should be able to inspect what the agent knows without reading source code.

### 7. Support manual debugging

Pause/resume should let users step outside agent routing without losing the agent’s passive notebook memory.

---

## Current project scope

The project includes:

- notebook hook registration,
- observation of every cell,
- natural-language cell routing,
- role-based OpenAI calls,
- root-level OpenAI provider config,
- root-level runtime config,
- structured assistant UI,
- copy-enabled code previews,
- explicit generated-code history,
- namespace diffing and provenance,
- safe auto-exec classification,
- one bounded repair retry for assistant-generated code,
- Python error review for failed user cells,
- pending proposal tracking,
- pause/resume/stop lifecycle controls,
- lightweight function/class metadata capture,
- public member and callable signature memory for classes,
- improved context selection based on symbol metadata,
- explicit display-oriented prompting for notebook-visible output,
- agent self-inspection helpers.

This is intentionally not a heavy multi-agent orchestration framework. It uses one runtime brain, several specialized logical roles, explicit registries, lightweight introspection, and a predictable notebook-first control flow.

---

## Short summary

Notebook Native Agent aims to make Jupyter feel like a **stateful autonomous coding workspace** where the assistant:

- understands natural-language notebook requests,
- stays grounded in the live runtime,
- proposes and safely executes code,
- remembers what was proposed and what actually ran,
- tracks symbol provenance and lightweight reusable-symbol semantics,
- repairs its own failed safe auto-runs once,
- helps review failed user Python cells without taking control away,
- supports pause/resume for manual debugging,
- remembers function and class semantics for intelligent follow-up reuse,
- and lets the user inspect what the agent currently knows.

In short:

**Natural-language Jupyter, with memory, provenance, safety, context awareness, and receipts.**
