# AGENTS.md

## What this is

`rai-scan` finds AI CLI agents, estimates disk usage, and removes them via recoverable trash. Single-package Python project, no third-party runtime dependencies.

## Commands

```sh
# dev setup
python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'

# test
.venv/bin/python -m pytest

# lint
.venv/bin/ruff check .

# run
.venv/bin/python -m rai_scan list --no-cache --verbose
```

Ruff config lives in `pyproject.toml`: `line-length = 100`, `target-version = "py38"`.

## Architecture

```
rai_scan/
  cli.py          # argparse entry point, main()
  scanner.py      # orchestrates probes, builds manifest, manages cache
  config.py       # state dir, signature loading/merging
  models.py       # dataclasses: Artifact, Package, ShellLine, DaemonEntry, AgentBundle
  safety.py       # permissions, symlink rejection, atomic writes
  signatures.json # bundled agent catalog (versioned, ~100 agents)
  classifier/     # matcher.py (classifies artifacts→agents), orphan.py, size.py
  probes/         # fs_probe, pkg_probe, shell_probe, daemon_probe, ai_related_probe
  removal/        # engine.py (trash + removal), rollback.py (signed journal)
  tui/            # guided.py (interactive menu)
```

Entry point: `rai_scan.cli:main` (wired via `pyproject.toml [project.scripts]`).

## Key behaviors

- `remove` command **always** forces a fresh scan (ignores cache).
- Scan cache expires after 5 minutes (`CACHE_MAX_AGE_SECONDS = 300`) and is keyed on scope + signature fingerprint.
- `~/.rai-scan/` is state dir (overridable via `RAI_SCAN_HOME` env var). Dir mode `0700`, files `0600`.
- Symlinked state, journal, and shell startup files are rejected.
- Custom signatures (`~/.rai-scan/signatures.json`) must stay inside `$HOME`, cannot target `.ssh`, `.gnupg`, or rai-scan state.
- Removal requires typing `YES`; system-scoped operations also require `SYSTEM`.
- Only the latest removal session can be rolled back.
- `--permanent` flag deletes files directly instead of moving to trash (cannot be undone).
- `purge` command permanently deletes all files in `~/.rai-scan/trash/`.

## Testing conventions

- Tests use `unittest.TestCase` (not pytest fixtures).
- Almost every test mocks `Path.home()` and sets `RAI_SCAN_HOME` to a `tempfile.TemporaryDirectory`. Follow this pattern for new tests.
- Run single test: `.venv/bin/python -m pytest tests/test_safety.py::SafetyTests::test_symlinked_shell_file_is_not_modified`
- The runtime has zero third-party dependencies; only `dev` extras (`pytest`, `ruff`).
