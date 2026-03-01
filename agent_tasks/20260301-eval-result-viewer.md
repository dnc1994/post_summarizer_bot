# Eval Result Viewer

## Context

The autorater produces a JSON results file, but there is no way to inspect it visually. This builds a result viewer modeled after the existing `eval_data_viewer.html`, supporting per-example inspection of generated summaries, rubric verdicts, and all LLM calls, plus a per-rubric filtering view.

---

## Todo

- [x] Extend autorater result file with article_text, LLM call logs, global rubrics
- [x] Print launch command at end of autorater run
- [x] Create `eval/launch_result_viewer.py`
- [x] Create `eval/eval_result_viewer.html`
- [x] Add `eval-result-viewer` target to Makefile

---

## 1. Autorater changes (`eval/autorater.py`)

### 1a. LLM call logging

`generate_summary` returns `(text, call_log)`. `evaluate_rubric` returns `({pass}, call_log)` and accepts `rubric_id` param. Dry-run summary emits `{dry_run: true, prompt: None}`. Per-example `llm_calls: []` list collects summary call log + each rubric call log.

### 1b. Extended result file fields

Each example object: `article_text`, `llm_calls`. Top-level: `global_rubrics`.

### 1c. Launch command printout

After saving:
```
To view results:
  make eval-result-viewer RESULT=eval/data/v2/results/<filename>.json
```

---

## 2. Launch script (`eval/launch_result_viewer.py`)

Modeled after `launch_data_viewer.py`. Read-only (no save endpoints).

```
Usage: uv run python eval/launch_result_viewer.py --result eval/data/v2/results/run.json [--port PORT]
```

- Binds to 127.0.0.1, auto-picks port if not specified
- Opens browser automatically
- One endpoint: `GET /` — serves `eval_result_viewer.html` with preloaded data injected at `<!-- __PRELOADED__ -->`

---

## 3. HTML viewer (`eval/eval_result_viewer.html`)

Self-contained SPA. Reuses CSS and layout patterns from `eval_data_viewer.html`.

**Header**: run metadata, overall pass rate badge, per-rubric badges (clickable to filter), active filter pill.

**Sidebar**: trace ID (8 chars), colored rubric dots (green/red per principle rubric), URL snippet. Filters to failing examples when a rubric filter is active.

**Detail pane — 5 tabs**:
| Tab | Content |
|-----|---------|
| Article | `article_text` in `.text-block` |
| Preview | `response` in `.rendered-block` |
| Response | `response` raw in `.text-block` |
| Rubrics | Table of rubric results; click row → filter sidebar |
| LLM Calls | Cards per call; prompt collapsible; dry-run label |

**Key implementation notes**:
- Use single-quoted string args in onclick (never `JSON.stringify` inside double-quoted HTML attributes — causes "Unexpected end of input")
- `toggleFilter(rubricId)` looks up statement from `globalRubrics` in JS; does not embed statement in onclick
- Read-only: no save buttons, no dirty state, no `beforeunload` guard
- File-picker fallback when `window.PRELOADED` is absent

---

## 4. Makefile

```makefile
eval-result-viewer:
    @test -n "$(RESULT)" || (echo "Error: Usage: make eval-result-viewer RESULT=eval/data/v2/results/run.json" && exit 1)
    uv run python eval/launch_result_viewer.py --result $(RESULT)
```

---

## Critical files

| File | Action |
|------|--------|
| `eval/autorater.py` | Modified |
| `eval/eval_result_viewer.html` | Created |
| `eval/launch_result_viewer.py` | Created |
| `Makefile` | Modified |
