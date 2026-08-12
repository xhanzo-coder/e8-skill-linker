# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-12

### Added

- Central skill library configuration with user and project scopes.
- Project-level Agent entry points for `.agents`, `.codex`, and `.claude`.
- Safe single and batch linking, unlinking, migration, and self-install flows.
- macOS/Linux symlink and Windows symlink or junction support.
- Git repository discovery, status, update, checkout, and clone workflows.
- Bilingual documentation, security policy, contribution guide, and CI.
- Cross-platform unit tests and standalone Agent Skill validation.

### Security

- Dry-run defaults for mutating operations.
- Authorized link-root checks and path traversal rejection.
- Non-destructive replacement backups for the global management skill.
- Batch preflight validation before any link is created.
- Fast-forward-only Git updates with dirty-tree and upstream checks.

[Unreleased]: https://github.com/xhanzo-coder/e8-skill-linker/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/xhanzo-coder/e8-skill-linker/releases/tag/v0.1.0
