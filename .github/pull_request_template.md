## Problem and result

Describe the concrete trigger, previous behavior, and resulting behavior.

## Validation

- [ ] `uv run --no-sync ruff check src tests scripts`
- [ ] `uv run --no-sync ruff format --check src tests scripts`
- [ ] `uv run --no-sync pytest -q`
- [ ] Relevant manual or platform-specific checks are described below.

## Safety and privacy

- [ ] Process actions still revalidate identity and ownership, or this change does not affect actions.
- [ ] No new process metadata leaves the machine, or the data flow is explicitly documented.
- [ ] No generated archives, model weights, credentials, or local configuration are included.
