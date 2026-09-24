# Performance architecture

Laya Top uses one long-lived collector, immutable snapshots and a retained terminal UI.
Collection runs in a worker thread; input, selection and drawing stay on the Textual event
loop. Core ML loads lazily in a separate bounded worker and never blocks process sampling.

## Performance budgets

Measure changes with:

```sh
.venv/bin/python scripts/benchmark_refresh.py
```

The target workload is approximately 1,000 processes or rows. The live collector section uses
the current host process set, so compare runs at similar counts; the render section uses 1,000
synthetic rows by default. The local timing budgets are:

- warm collection p95 below 100 ms;
- unchanged table refresh p95 below 25 ms.

The related behavioral requirements are:

- no full table clear when process identities and columns are unchanged;
- no model load when AI is disabled or all sampled software matches local rules.

The timing values are regression thresholds, not universal product guarantees. Process
permissions, kernel load, terminal implementation and container activity materially affect
measurements.

## Current design

- `psutil.process_iter()` keeps process handles across refreshes. `oneshot()` groups fields
  backed by the same operating-system call. Stable executable and ownership metadata use a
  separate cache from fast CPU and RSS counters.
- Process identity is `(PID, creation time)`. Rendering and process actions never rely on a
  PID alone, which prevents a reused PID from inheriting state or receiving an intended signal.
- DataTable rows use immutable identity keys. A refresh calculates lightweight signatures,
  updates changed cells only, and sorts only when row order changes.
- Classification rules, application names, hierarchical labels and parsed search queries are
  bounded or per-object caches. Model suggestions have their own bounded queue and LRU cache.

This follows the performance guidance in the
[psutil API](https://psutil.io/api/), which recommends `process_iter()` and `oneshot()` for
batched process reads, and the
[Textual DataTable API](https://textual.textualize.io/widgets/data_table/), which provides
keyed cell updates, row removal and in-place sorting.

## Rust decision

A full Rust rewrite is not justified by the measured macOS hot path. psutil already performs
the kernel calls in native code; after caching, warm collection is tens of milliseconds for
roughly 1,000 processes. The larger remaining cost was Python presentation allocation, which
can be removed without changing the application or packaging model.

Rust remains a useful option if measurements cross the budgets above on supported Linux hosts
or if single-binary distribution becomes a primary requirement. The preferred sequence would
be:

1. Add Linux CI and benchmark the same workload and process counts.
2. Prototype only the collector behind the existing snapshot interface using
   [`sysinfo`](https://docs.rs/sysinfo/latest/sysinfo/struct.System.html). Configure
   `ProcessRefreshKind` to fetch CPU, memory and only-if-missing executable metadata; do not
   refresh Linux tasks unless requested.
3. Compare end-to-end latency, idle CPU, RSS, cold start and wheel size. Keep the Python
   collector as a fallback until native wheels cover macOS ARM64/x86_64 and Linux glibc/musl.
4. Consider a full
   [Ratatui](https://ratatui.rs/faq/) application only when the product accepts replacing
   Textual and the Python-only Core ML integration. Ratatui redraws through a diffed terminal
   buffer, but a rewrite would also recreate the tested interaction and safety layers.

Native Python modules require platform wheels. PyO3 recommends `maturin` for that build and
distribution workflow; its [distribution guide](https://pyo3.rs/main/building-and-distribution)
also documents the stable ABI tradeoffs. Mature monitors such as
[`bottom`](https://github.com/ClementTsang/bottom),
[`btop`](https://github.com/aristocratos/btop) and
[`htop`](https://github.com/htop-dev/htop) demonstrate the attainable native design, while
also showing the platform-specific collection code and release matrix a rewrite would inherit.
