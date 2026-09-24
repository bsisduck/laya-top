# Contributing to laya-top

Thank you for improving laya-top. Focus each change on one user-visible problem or one maintainability concern, and open an issue first when a proposal changes process-control policy, privacy boundaries, platform support, or the category vocabulary.

## Set up the project

Use Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/bsisduck/laya-top.git
cd laya-top
uv sync --frozen --extra dev
```

Add `--extra laya` only on an Apple Silicon Mac where you intend to exercise Core ML. Model weights are never required for the normal test suite.

## Make and validate a change

Create a focused branch from current `main`. Preserve the immutable `(PID, creation time)` action boundary, keep blocking work off Textual's event loop, and add tests at the boundary whose behavior changes.

```sh
uv run --no-sync ruff check src tests scripts
uv run --no-sync ruff format --check src tests scripts
uv run --no-sync pytest -q
uv build
```

The signal integration test creates and controls its own disposable Python child. It never targets an existing process. Run process-access tests in a normal terminal if a sandbox denies inspection.

Update `README.md`, `ARCHITECTURE.md`, or `CHANGELOG.md` when behavior, constraints, or public interfaces change. Do not commit model weights, build output, screenshots, local labels, secrets, or environment-specific configuration.

## Submit the change

Write commits that explain why the change is needed. In the pull request, describe the trigger and resulting behavior, list the validation you ran, and call out any platform-specific limit. By contributing, you agree that your contribution is licensed under the repository's [MIT License](LICENSE).

Report security problems through [the private process](SECURITY.md), not a public issue.
