# Changelog

All notable project changes are documented here.

## 0.1.1 — 2026-07-15

Safety hardening and bug fixes.

### Fixed

- `purge` now reports the true number of removed files instead of top-level trash entries.
- A failed or interrupted file move no longer leaves a phantom "moved to trash" journal entry.
- Guided menu and CLI now use the same `SYSTEM` keyword for system-scoped confirmation.

### Safety

- Directory removals refuse top-level and nested mount points, preventing unmount of filesystems.
- Artifact identity (device, inode, mode, owner) is re-verified immediately before each deletion to defeat time-of-check/time-of-use symlink swaps.
- Per-artifact failures are isolated; a single bad artifact no longer aborts the rest of an agent's removal.
- Hidden agent directories and files (e.g. `.codex`, `.agents`) delete with the same scope, identity, and mount-point protections as any other path.

## 0.1.0 — 2026-06-23

Initial public release.

### Features

- Signature-based discovery of AI CLI binaries, packages, configuration,
  caches, shell lines, and systemd units.
- Conservative low-confidence reporting for other AI-related data.
- Terminal, JSON, Markdown, and HTML reports.
- Guided menu and command-line removal workflow.
- Recoverable trash and rollback support.
- Custom user signature overrides.
- Bundled AI-agent signature catalog.

### Safety

- Owner-only state directories and files.
- Signed rollback journals with a private integrity key.
- Rollback schema, source-confinement, and destination validation.
- Artifact identity checks using device, inode, mode, owner, size, and mtime.
- Package scope detection and explicit system-operation confirmation.
- Protected system-tree and sensitive user-path denylists.
- Safe custom-signature validation.
- Collision-resistant trash paths.
- Atomic shell-file replacement with non-UTF-8 byte preservation.
- Root execution refusal for installation, removal, rollback, and uninstall.
- Fresh scans before CLI and guided removals.
- Same-filesystem atomic file removal and restoration.
- Package and systemd identifier validation before subprocess execution.
- Daemon rollback that restores recorded enabled and running state.
- Fail-closed handling of incomplete package and daemon operations.

### Project

- Dependency-free Python runtime.
- Automated tests and Ruff linting.
- GitHub Actions across supported Python versions.
- MIT license, security policy, and installation documentation.
