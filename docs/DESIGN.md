# Design and implementation plan

## Product

Make a busy machine understandable: what is running, which application it belongs
to, what is consuming resources, and how to stop a specifically selected process.
The first release targets macOS and Linux, with an optional Apple Silicon Laya
backend. It is a working process manager, not an autonomous cleanup agent.

## Interaction

- Live CPU, RAM, swap, network and disk activity with short resource histories.
- A keyboard/mouse process table, stable process selection, sortable columns,
  search operators, tree mode, category overview and drill-down.
- Explainable category/subcategory labels; application grouping; user overrides.
- An inspector with executable, owner, parent, age, threads and tag provenance.
- Explicit terminate, force kill, suspend and resume dialogs. Escape cancels.
- A demo mode, headless JSON snapshot, diagnostic command and explicit model download.

## Architecture

1. `collector`: psutil reads, independent of the terminal; CPU uses deltas by
   (PID, creation time) so a reused PID cannot inherit an old CPU counter. Process
   handles, static metadata and short-lived state are cached at different cadences.
2. `tagging`: deterministic executable/name rules first, user overrides above them.
   Rules derive subcategories without another model call. Laya only proposes broad
   categories for unknown software. Categories never authorize actions.
3. `intelligence`: one daemon worker, bounded queue and LRU cache. Inference cannot
   block sampling or keyboard input. No automatic model downloads. No command-line
   arguments, environment variables or file contents enter a model prompt.
4. `actions`: re-open PID, compare creation time, check ownership and protections,
   then call psutil's PID-reuse-aware signal methods. No shell, sudo, automatic
   escalation or recursive termination. UI confirmation captures an immutable target.
5. `app`: Textual screen and modals; psutil sampling runs off the UI thread. Each
   snapshot is immutable. Keyed rows update changed cells, add or remove individual
   process identities, and reorder only when needed; selection follows process identity
   rather than row number.
6. `cli/config`: installable Python entry point, explicit local paths, diagnostics,
   machine-readable snapshots and atomic per-user category overrides.

## Constraints

- CPU can exceed 100% for a multithreaded process (100% = one logical core).
- RSS is not exclusive memory; adding RSS may double-count shared pages.
- System/other-user processes are visible but cannot be controlled here. Current
   process and ancestor chain are protected even when running as root.
- No per-process GPU/ANE power claims: psutil does not expose those metrics.
- The installed ANE model has a 96-token ceiling. Prompts are compact and tested
   against the tokenizer; unavailable/uncertain inference leaves an honest unknown tag.
- AI scores describe its output distribution, not measured correctness.

## Validation

Unit tests for rules, filters, identity checks, cache behavior and protection.
Integration tests send signals only to disposable subprocesses created by the test.
Textual headless tests cover filtering, selection under reordering, modals, group
navigation, empty results and small windows. Verify packaging and the local Core ML
adapter separately, then inspect a rendered terminal screenshot.

## Future work

Evaluate a labeled process corpus before claiming classification accuracy. Consider
Linux ONNX, GPU providers, explicit process-family operations, historical storage,
and signed release artifacts only after the single-process workflow is established.
