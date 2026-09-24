# laya-top

**Know what is running. Understand the tags. Stay in control.**

A keyboard-and-mouse terminal process monitor inspired by htop and asitop, with
explainable software categories, useful subcategories, and optional **local Laya inference**. Built with
Python, Textual and psutil. Original project code is **MIT licensed**.

```text
 LAYA TOP                                    Know what is running.
 CPU 24.8%       MEMORY 17 / 32 GiB           NETWORK ↓ 47 KiB/s
 ─────────────────────────────────────────────────────────────────
 PID   PROCESS         CATEGORY / SUBCATEGORY    CPU %    MEMORY
 4101  ollama          AI / Inference             134.2    6.7 GiB
 4102  Code            Development / Editor        18.4    830 MiB
 4104  Google Chrome   Browser / Browser            12.6    1.2 GiB
 4110  custom-tool     Development ~                 0.0     24 MiB
 ─────────────────────────────────────────────────────────────────
 / Search   T Tree   G Categories   K Stop   L Label   ? Help
```

Illustrative layout and values. `~` means a model suggestion, not a verified fact.

## Install and run

From a downloaded or cloned project directory:

```sh
./install.sh
./laya-top
```

The installer uses **uv** when available, selects Python 3.12 and installs from
`uv.lock` into the project's `.venv`. uv may download Python if necessary. Without
uv, the installer uses an existing Python 3.11–3.13 and pip; this fallback resolves
the version ranges in `pyproject.toml`. Both paths keep dependencies isolated.
No sudo, shell-profile changes or automatic model download.

On macOS, you can also double-click **`launch.command`** after installing.

For a PATH command in a separate tool environment, with uv installed:

```sh
uv tool install --python 3.12 '.[laya]'
laya-top
```

This installs from your local checkout. This project is not published to PyPI yet.
For the monitor without optional model dependencies, use `./install.sh --no-ai`
or `uv tool install --python 3.12 .`.

## Enable local intelligence

The monitor is immediately usable with software rules. On an **Apple Silicon Mac
with macOS 15+**, install the default extra, then explicitly download the model:

```sh
./laya-top model download
./laya-top
```

The default ANE FP16 bundle is approximately 650 MB. It is stored under
`~/.cache/laya-top/model` (or `$XDG_CACHE_HOME/laya-top/model`). Model loading can
take a minute or more on first use; the process monitor remains responsive.

Reuse an existing local model:

```sh
./laya-top --model /path/to/laya-multilingual-coreml-ane
# Or:
export LAYA_TOP_MODEL=/path/to/model
./laya-top
```

Discovery order: `--model`, `LAYA_TOP_MODEL`, the cache directory, `./models/snake`,
then `../laya-coreml/models/snake`. The project launcher sets its working directory
to the checkout, so an adjacent Laya Snake installation is reused automatically.

```sh
./laya-top --no-ai                # deterministic categories only
./laya-top doctor                 # environment and process-access diagnostics
./laya-top doctor --check-model   # actual inference on a synthetic software name
./laya-top model path             # selected/default model directory
```

No inference request accesses the network. Only the explicit `model download`
command downloads weights. The installed Laya backend and weights are third-party
Apache-2.0 components; they are not relicensed to MIT. See [NOTICE](NOTICE).

## What you can do

- Monitor host CPU, memory, swap, uptime, network and disk throughput.
- Read fixed-scale CPU and memory histories covering the last 60 samples.
- Sort processes by CPU, resident memory, name, PID or age. Click supported column
  headings again to reverse sorting. 100% process CPU means one logical core.
- Explore parent-child relationships in **Tree** view and resource totals in
  hierarchical **Categories** view. Enter on a category/subcategory opens its members.
- Search software, application families, owners, PIDs, states and tags.
- Pin interesting processes above the current sort with **F**.
- Inspect a process's executable, owner, parent, lifetime, threads and tag reason.
- Override a software category with **L**; labels survive restarts.
- Request graceful stop, force kill, pause or resume for an eligible process.
- Review a bounded, in-memory action history for the current session.
- Export read-only JSON snapshots for scripts and investigations.

The layout fits the terminal as you resize it, including while updates are frozen.
Process names expand into available space; secondary columns and the side inspector
hide when space is tight. **Enter** opens all process details in a scrollable dialog.
Short windows collapse the graphs and view buttons to leave room for process rows;
their keyboard shortcuts remain available. **80 × 24** fits the core columns without
horizontal scrolling; **145 × 35** or larger also shows the side inspector.
Colors respect `NO_COLOR`.

## Controls

| Key | Action |
| --- | --- |
| Up/Down, PageUp, PageDown | Navigate processes |
| `/` | Focus search |
| Enter | Inspect process / open category / finish searching |
| Escape | Leave search, clear search, or cancel a dialog |
| `T` / `G` | Toggle tree / category overview |
| `M` | Toggle only your processes |
| `C` / Shift+`M` | Sort by CPU / memory |
| `S` | Cycle sort field |
| `F` | Pin or unpin selected process |
| `L` | Set/reset category for this executable |
| Space | Freeze/resume the displayed snapshot |
| `K` | Request graceful stop (SIGTERM) |
| Shift+`K` | Force kill (SIGKILL), after typing the PID |
| `P` / `R` | Pause (SIGSTOP) / resume (SIGCONT) |
| `A` | Session action history |
| `?` / `Q` | Help / quit |

Letter shortcuts are lowercase unless explicitly marked **Shift**. Buttons and
the footer also accept mouse clicks. Every process signal requires confirmation;
Cancel is focused by default. No signal is sent by merely selecting a row.

## Search

Terms combine with **AND**. Prefix a term with `-` to exclude it. Quote text with
spaces. Memory comparisons use **MiB**; CPU comparisons use percent of one core.

```text
tag:AI
sub:Runtime
app:"Google Chrome"
user:alice state:running
cpu>5 mem>100
-tag:System python
source:Laya
pid:1234
```

## How tagging works

1. **You** — a saved category for an exact executable path (or name when the OS
   does not expose its path).
2. **Rule** — known software names, macOS application bundles and system locations.
3. **Laya** — a local suggestion for software not covered by those rules.
4. **Unknown** — insufficient information, unavailable model, or inconclusive output.

Categories remain stable: **AI, Development, Browser, Communication, Media,
System, Other**. Local rules add narrower labels such as **Inference, Editor,
Runtime, Database, Renderer, Chat, Audio, Desktop**, and **Virtual machine**.
Laya still makes one coarse-category inference; deterministic name rules derive
the subcategory without a second model call. Rule matching is heuristic too: a
renamed executable may be misclassified.

The model receives only a short process name and application name. It never gets
command-line arguments, environment variables, usernames, full executable paths,
file contents or network traffic. One background worker handles at most two new
classifications per second, with a 64-item queue and 512-result in-memory LRU cache.
The ANE prompt fits within 96 tokens; long names are shortened against the actual
tokenizer. The UI continues to sample while the model loads or predicts.

A suggestion requires a top probability of at least 0.70 and a 0.15 lead over the
runner-up. These are conservative display heuristics, **not validated accuracy
thresholds**. Laya can be confidently wrong. Use your own labels when necessary.
No model output can trigger a signal or override process protection.

## Process controls and privacy

- Actions address a single `(PID, creation time)` identity, never a row number.
  Identity and current ownership are checked immediately before signaling.
- Root-owned processes, other users' processes, essential session processes,
  laya-top itself and its ancestor chain are protected. An unreadable ancestor
  chain disables controls. Running with sudo does not bypass this policy.
- SIGTERM requests graceful exit; it does not guarantee exit. There is no timed
  or automatic escalation to SIGKILL. Force kill needs a separate confirmation.
- No recursive process-tree kill, group kill, automatic cleanup or cloud telemetry.
- Labels are the only normal persistent app data, saved atomically to
  `~/.config/laya-top/labels.json` (or `$XDG_CONFIG_HOME/laya-top/labels.json`).
- Action history and AI caches are memory-only. JSON snapshots deliberately
  include process names, owners and executable paths, so review them before sharing.

## Headless mode and demos

```sh
./laya-top snapshot --count 20 > snapshot.json
./laya-top --demo                 # illustrative data; real controls disabled
./laya-top --demo snapshot --count 5
./laya-top --interval 1           # refresh every second; supported range 0.5–30
```

Snapshots use rules and saved labels; they do not start the model. Demo labels are
session-only and never modify your saved configuration.

The collector reuses process handles and caches stable metadata instead of reading
executable paths and usernames every refresh. The table keeps rows by immutable
process identity, updates changed cells, and reorders them in place. On machines
where model memory is more important than local suggestions, `--no-ai` avoids
loading Core ML while retaining rules and subcategories.

## Development

```sh
uv sync --frozen --extra dev --extra laya
uv run --no-sync ruff check src tests scripts
uv run --no-sync ruff format --check src tests scripts
uv run --no-sync pytest -q
uv build
uv run --no-sync python scripts/capture_demo.py
```

Omit `--extra laya` on machines without Core ML. Tests exercise filtering,
classification caching, UI interaction, stable selection, reused PIDs and process
protection. The signal integration test creates its own disposable Python child;
it never targets an existing user process. A restrictive sandbox may block OS
process inspection; run these checks in your normal terminal.

Screenshots and distribution archives are generated under ignored `artifacts/`
and `dist/` directories. See [DESIGN.md](docs/DESIGN.md) for architecture, scope,
validation strategy and the next development steps.

## Platform status and limits

- **Validated locally:** Apple Silicon, macOS 27, Python 3.12, real Core ML inference.
- **Designed for Linux:** psutil monitoring, tags and POSIX controls. Linux has
  not yet been exercised on a real Linux host in this release. Core ML is macOS-only.
- **Windows:** not supported in this release.
- GPU/ANE utilization, power sensors and per-process network rates are not
  available. Unlike asitop, this version does not invoke privileged power tools.
- OS-protected or very short-lived processes may be missing. Permission-restricted
  executable paths may be blank. The first CPU sample establishes a baseline.
- RSS includes shared memory, so category totals are not unique physical usage.
- Laya categories have not been benchmarked against a labeled process dataset.

## License and acknowledgments

[MIT](LICENSE) for laya-top. Thanks to [Textual](https://github.com/Textualize/textual),
[psutil](https://github.com/giampaolo/psutil),
[Laya](https://github.com/NandhaKishorM/laya), and
[Laya-CoreML](https://github.com/mizorewww/laya-coreml).
Dependency and model licenses remain their own; see [NOTICE](NOTICE).
