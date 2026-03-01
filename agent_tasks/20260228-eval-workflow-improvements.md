# Eval Workflow Improvements

## Context

The eval tooling needs clearer semantics, immutability guarantees, and a better viewer UX.

## Design Decisions (updated)

- **"Ready for eval" persistence**: `examples.jsonl` per dataset version (committed). Each record: `{ "trace_id": "...", "eval_ready": true }`. Replaces the originally proposed `eval_ready.json`.
- **Global rubrics file**: `global_rubrics.jsonl` (JSONL format, one rubric per line). Replaces `rubrics.json` (JSON array). Example-specific rubrics remain in `example_rubrics.jsonl`.
- **`gen_rubrics.py` merge strategy**: Load existing rubrics from `global_rubrics.jsonl`, generate new ones, append only those with novel statements (case-insensitive dedup). No interactive prompt.
- **Tab ordering**: Article | Preview | Response | Prompt | Rubrics | Global Rubrics | Metadata
- **File renames**: `viewer.html` → `eval_data_viewer.html`, `launch_viewer.py` → `launch_data_viewer.py`. Title: "Eval Data Viewer".
- **Global Rubrics in viewer**: Read-only tab displaying `global_rubrics.jsonl` content.

## Files to Modify/Create/Rename

| File | Change |
|------|--------|
| `eval/gen_rubrics.py` | Use `global_rubrics.jsonl` (JSONL), merge-safe (append-only, dedup) |
| `eval/autorater.py` | Use `global_rubrics.jsonl`; filter traces by `eval_ready` from `examples.jsonl` |
| `eval/launch_data_viewer.py` | Renamed from `launch_viewer.py`. Serve `global_rubrics.jsonl` + `examples.jsonl`; new `/save-examples` endpoint |
| `eval/eval_data_viewer.html` | Renamed from `viewer.html`. Full UI overhaul |
| `eval/launch_viewer.py` | Delete (replaced by `launch_data_viewer.py`) |
| `eval/viewer.html` | Delete (replaced by `eval_data_viewer.html`) |
| `Makefile` | Update `eval-viewer` to use `launch_data_viewer.py` |
| `CLAUDE.md` | Update docs for new concepts and filenames |

## Data File Layout (per version)

```
eval/data/<version>/
  traces.jsonl          # gitignored — scraped article content (dump_traces.py output)
  examples.jsonl        # committed — per-example metadata: { trace_id, eval_ready }
  global_rubrics.jsonl  # committed — global rubrics, one per line (was rubrics.json)
  example_rubrics.jsonl # committed — example-specific rubrics
  results/              # gitignored — per-run score reports
```

## Todo

- [x] Task 1: gen_rubrics.py — use global_rubrics.jsonl (JSONL) + merge-safe
- [x] Task 2: launch_data_viewer.py — renamed, serve global_rubrics.jsonl + examples.jsonl, new endpoints
- [x] Task 3: autorater.py — use global_rubrics.jsonl; filter by examples.jsonl eval_ready
- [x] Task 4: eval_data_viewer.html — renamed, full UI overhaul (tabs, URL, toggle, counts, rename)
- [x] Task 5: Makefile + file cleanup (delete old viewer.html, launch_viewer.py)
- [x] Task 6: CLAUDE.md docs update

## Task Details

### Task 1: gen_rubrics.py — global_rubrics.jsonl + merge-safe

Change:
- `rubrics_file = data_dir / "rubrics.json"` → `global_rubrics_file = data_dir / "global_rubrics.jsonl"`
- Remove interactive "Overwrite? [y/N]" prompt (lines 183-198)
- Replace with merge logic:
  1. Load existing rubrics from `global_rubrics.jsonl` as JSONL (or empty list)
  2. Generate new candidates via Gemini
  3. Dedup: skip candidates whose `statement.strip().lower()` matches any existing
  4. Renumber new rubric IDs to continue from highest existing ID (e.g. if max is r5, new ones start at r6)
  5. Write merged list (existing + new) to `global_rubrics.jsonl` as JSONL, only if there are additions
  6. Print summary: "Merged: X existing + Y new = Z rubrics" or "No new rubrics to add"

### Task 2: launch_data_viewer.py — new file

Create `eval/launch_data_viewer.py` as a modified copy of `launch_viewer.py` with:
- References updated to `eval_data_viewer.html` (not `viewer.html`)
- Load `global_rubrics_file = data_dir / "global_rubrics.jsonl"` as JSONL list
- Load `examples_file = data_dir / "examples.jsonl"` as JSONL list
- Include `globalRubrics` (list of rubric objects) and `examplesMetadata` (list of {trace_id, eval_ready}) in preloaded data
- Re-read all three files (example_rubrics, global_rubrics, examples) on each GET `/`
- Add `POST /save-examples` endpoint: receives JSONL body, writes to `examples.jsonl`
- Update print summary to show global rubric count and examples metadata count

### Task 3: autorater.py — eval_ready filter + global_rubrics.jsonl

Changes:
- `rubrics_path = ... / "rubrics.json"` → `rubrics_path = ... / "global_rubrics.jsonl"`
- Read rubrics as JSONL (not JSON array)
- After loading traces (line 184-186), load `examples.jsonl`:
  - Parse to map: `{ trace_id → eval_ready_bool }`
  - If file exists and has any `eval_ready: true` entries: filter traces to only those, print count
  - If file missing or empty or no eval_ready entries: warn and evaluate all traces (backward compatible)

### Task 4: eval_data_viewer.html — full UI overhaul

**4.0 File rename + title:**
- New file: `eval/eval_data_viewer.html`
- `<title>Eval Data Viewer</title>`
- `<h1>Eval Data Viewer</h1>`

**4.1 Clickable URL:**
- Detail header URL: wrap in `<a href="..." target="_blank">` with appropriate styling

**4.2 Tab order:** Article | Preview | Response | Prompt | Rubrics | Global Rubrics | Metadata
```js
const TABS = [
  { id: 'article_text', label: 'Article',        field: 'article_text' },
  { id: 'rendered',     label: 'Preview',        field: 'response',     render: true },
  { id: 'response',     label: 'Response',       field: 'response' },
  { id: 'prompt',       label: 'Prompt',         field: 'prompt' },
  { id: 'rubrics',      label: 'Rubrics',        custom: true },
  { id: 'global_rubrics', label: 'Global Rubrics', custom: true },
  { id: 'metadata',     label: 'Metadata',       custom: true },
];
```
Default active tab: `'article_text'`

**4.3 Rubrics tab (was rubrics-panel below tabs):**
- Remove `.rubrics-panel` from below tabs in `renderDetail()`
- Rubric editing UI moves into the `rubrics` tab panel
- Keep all existing edit/add/delete functionality

**4.4 Global Rubrics tab (read-only):**
- Display rubrics from `window.PRELOADED.globalRubrics` (list of `{id, statement, rationale}`)
- Rendered as read-only rubric items (no edit/delete buttons)
- Empty state: "No global rubrics. Edit `global_rubrics.jsonl` directly or run `make eval-rubrics`."

**4.5 Metadata tab:**
- Display: rating badge, timestamp, user comment
- Move these from detail header sub-row to this tab

**4.6 Detail header (slimmed down):**
- Keep: clickable URL (full), trace_id (small monospace), "Ready for eval" toggle button
- Remove from header: rating badge, timestamp, user comment (moved to Metadata tab)

**4.7 "Ready for eval" toggle:**
- New state: `evalReady = new Set()` — populated from `examplesMetadata` on load
- Button in detail header:
  - Active (in set): green background, label "✓ Ready for eval"
  - Inactive: outline button, label "Mark ready for eval"
- Sidebar list item: show green "✓" indicator before trace_id if in evalReady set
- On toggle: update set, POST to `/save-examples` (JSONL of `{trace_id, eval_ready}` for all traces), re-render list

**4.8 Sidebar cleanup:**
- Show: trace_id (8 chars), ready indicator (✓), rubric count, URL
- Remove from sidebar: rating badge (👍/👎), user comment snippet

**4.9 Counts:**
- Remove sidebar header counts (`sidebar-hd`)
- Keep only header-controls counts: "X ready · Y total" (right side, next to export button)

### Task 5: Makefile + file cleanup

- Update `eval-viewer` Makefile target to use `launch_data_viewer.py` instead of `launch_viewer.py`
- Delete `eval/viewer.html`
- Delete `eval/launch_viewer.py`

### Task 6: CLAUDE.md docs update

- Update file tree to show `global_rubrics.jsonl`, `examples.jsonl`, and renamed viewer files
- Update viewer description (name: "Eval Data Viewer", scripts: `launch_data_viewer.py`)
- Note `gen_rubrics.py` now merges instead of overwriting
- Document `examples.jsonl` and "ready for eval" concept
- Update `make eval-viewer` description
- Remove reference to `rubrics.json`

## Verification

1. Run `make eval-viewer VERSION=v1` — verify:
   - Opens "Eval Data Viewer" title
   - Tab order: Article, Preview, Response, Prompt, Rubrics, Global Rubrics, Metadata
   - URL in detail header is clickable
   - Global Rubrics tab shows empty-state message (no global_rubrics.jsonl yet)
   - Rubrics tab has editing UI (move/add/delete)
   - Metadata tab shows rating, timestamp, comment
   - Detail header: only URL + trace_id + ready toggle
   - Sidebar: trace_id, ready indicator, rubric count, URL
   - Counts in top-right only ("X ready · Y total")
   - Toggle "ready" → check `examples.jsonl` written to disk
2. Run `gen_rubrics.py` twice on v1 — second run: "No new rubrics to add"
3. Run `autorater.py` with some traces marked ready → confirms it filters correctly
