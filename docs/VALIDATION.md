# Local validation — 2026-09-24

Tested on Apple Silicon, macOS 27.0, Python 3.12.13, Textual 8.2.8,
psutil 7.2.2 and laya-coreml 0.1.0.

- 37 automated tests passed, including a real disposable child process for
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
- At 1,038 processes, reusing process handles and metadata reduced a warm collection
  cycle from 0.978 to 0.553 seconds (43%). At 854–1,043 rows, an unchanged table
  render fell from a 0.353-second median to 0.019 seconds (about 18×). A later live
  end-to-end refresh, including collection, tagging and rendering, had a 0.101-second
  median across 902 processes. The host had concurrent Docker saturation, so these
  are local regression measurements rather than general performance guarantees.
- Wheel and source archives built successfully; the wheel includes the TUI stylesheet.
- Real offline Core ML inference on the synthetic name `Google Chrome` returned
  the Browser category. Model loading took 84.47 seconds; the first prediction
  took 79.78 ms. These include cold-start effects and are not steady-state benchmarks.

This establishes integration, not classification accuracy. No labeled process
corpus was evaluated. Linux, Intel Macs, other macOS releases and Python 3.11/3.13
have not been exercised on physical hosts in this release. Published model/runtime
requirements are documented separately from what was tested here.
