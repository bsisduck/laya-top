# Local validation — 2026-09-24

Tested on Apple Silicon, macOS 27.0, Python 3.12.13, Textual 8.2.8,
psutil 7.2.2 and laya-coreml 0.1.0.

- 40 automated tests passed, including a real disposable child process for
  suspend, resume and SIGTERM, plus mocked reused-PID and ownership-change cases.
- Terminal interaction tests covered searching, category drill-down, tree view,
  pinning, labels, freeze, small windows, dialog cancellation, force-kill PID
  entry, stable selection after sorting, and immutable confirmation targets.
- Resize regressions cover process, tree and category views from 40 × 12 to
  180 × 50, shrinking and growing while frozen, preserving the selected target,
  resizing during confirmation, and header sorting after optional columns hide.
  Tables fit without horizontal scrolling; memory values retain their units.
- The documented `./install.sh` completed successfully from `uv.lock`.
- Live process inspection saw more than 1,000 processes. A real PTY session
  started and exited with Q without an error. No existing process was signaled.
- Full and compact screenshots were exported from the actual Textual UI with
  illustrative hierarchical categories and visually inspected. Reproduce with
  `scripts/capture_demo.py`.
- Initial caching reduced a warm 1,038-process collection cycle from 0.978 to 0.553
  seconds while the host was saturated. In the final quieter 30-iteration run, 881
  processes took 17.3 ms median and 18.5 ms p95 after a 117.0 ms cold sample.
- A profiled unchanged 960-row render fell from 21.6 to 6.9 ms after styled-cell
  allocation became conditional. The final unprofiled 1,000-row run measured 3.6 ms
  median and 6.8 ms p95. Tests verify that an unchanged refresh performs no row clear,
  cell update or sort.
- Incremental add/remove reconciliation prevents one short-lived process from rebuilding
  the complete table. Under the same profiled live workload, end-to-end refresh median
  fell from 159.2 to 74.7 ms across roughly 950 processes. Host load still affects these
  local regression measurements; they are not general performance guarantees.
- An aggressive rules-only TUI run used approximately 60 MiB RSS. This is a single-host
  observation rather than a memory guarantee.
- Wheel and source archives built successfully; the wheel includes the TUI stylesheet.
- Real offline Core ML inference on the synthetic name `Google Chrome` returned
  the Browser category. Model loading took 84.47 seconds; the first prediction
  took 79.78 ms. These include cold-start effects and are not steady-state benchmarks.

This establishes integration, not classification accuracy. No labeled process
corpus was evaluated. Linux, Intel Macs, other macOS releases and Python 3.11/3.13
have not been exercised on physical hosts in this release. Published model/runtime
requirements are documented separately from what was tested here.
