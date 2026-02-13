# UI Decomposition Plan (`ui/app.js`)

## Goal
Reduce `ui/app.js` size and coupling without changing behavior, build tooling, or runtime architecture.

Constraints:
- Keep the current static loading model (no bundler required).
- Preserve existing routes, state model, and API contracts.
- Extract in small slices to reduce regression risk.

## Current Shape
- Single file owns: state, routing, API helpers, page rendering, memory tabs, settings, configure forms, and event wiring.
- Main pain: difficult local reasoning and higher chance of incidental breakage.

## Target Shape (Incremental)
1. `ui/app.js` remains bootstrap + shared app state.
2. Extract page modules loaded via additional `<script>` tags:
   - `ui/modules/memories.js`
   - `ui/modules/notes.js`
   - `ui/modules/settings.js`
   - `ui/modules/configure.js`
3. Keep utility layer centralized:
   - `apiFetch`, `runMutationAction`, toast, formatting, shared bind helpers.

## Extraction Order
### Slice 1 (first, lowest risk)
Extract Memories tab rendering + handlers:
- `renderMemoriesPage`
- `renderWorkingMemory`
- `renderSemanticMemory`
- `renderDeepMemory`
- associated bind/upload/preview helpers

Why first:
- Already grouped conceptually.
- Clearly bounded by `state.memoriesSubTab` and memory APIs.
- Minimal coupling to configure/settings forms.

### Slice 2
Extract Notes page implementation and note review actions.

### Slice 3
Extract Settings page + provider cards and daemon controls.

### Slice 4
Extract Configure/editor sections last (highest coupling).

## Implementation Pattern
For each slice:
1. Move functions to `ui/modules/<slice>.js`.
2. Expose module API on `window.MemorableModules.<slice>`.
3. Keep `app.js` calls, but delegate:
   - before: `renderSemanticMemory(container)`
   - after: `window.MemorableModules.memories.renderSemanticMemory(ctx, container)`
4. Add smoke checks before/after extraction:
   - page loads
   - actions mutate server state
   - no console errors

## Ready-to-Start PR Scope
PR title: `refactor(ui): extract memories module from app.js`

Changes:
- Add `ui/modules/memories.js`.
- Move Memories-related functions from `app.js`.
- Wire module in `ui/index.html` before `app.js`.
- Keep functionality identical.

Validation:
- manual nav through Memories sub-tabs
- upload/process in Semantic and Deep
- regenerate now/knowledge
- deep search works

## Success Metrics
- `ui/app.js` reduced by at least 20% after first two slices.
- No route/action regressions.
- Lower blast radius for future feature work.
