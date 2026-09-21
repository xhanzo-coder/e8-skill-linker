# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Per-command `--library` selection for installation, linking, checks and updates; `--all-libraries` for checks and update discovery.
- Registry-driven update reports with cache/fetch freshness, changed files, affected installed skills and available unexposed skills.
- Pre-update validation of registered skills in the candidate commit, followed by exact-commit fast-forward and post-update verification.
- Repository reuse for adding skills and enabling existing skills in another project, with rollback limited to new entries.
- Local Git integration tests for multiple-library isolation, update failures and junction retargeting.

### Fixed

- Preserve the central entry as the immediate target of Windows project junctions.
- Accept repository-root skills whose frontmatter name differs from the repository name.
- Keep self-install backups outside global skill discovery directories.
- Preserve complete repository namespaces in storage identities.

### Breaking

- `updates` uses configured library names and registered repositories; remove arbitrary `--central` selection and legacy root-repository discovery.
- Existing project links flattened into `.repos` require explicit unlink/relink to use the stable central entry.
- `update` no longer accepts `--allow-dirty`; origin or HEAD drift from the registry must be resolved explicitly.

## [0.2.0] - 2026-09-04

### Added

- Schema v2 configuration with multiple named central libraries and one explicit active library.
- Explicit `migrate-config`, `library-list`, `library-add`, and `library-use` workflows.
- Transactional `install-repo` support that keeps complete Git repositories under `.repos`, creates central and optional project entries, and records provenance in `.skill-linker-lock.json`.
- Git repository discovery inside the hidden `.repos/<host>/<owner>/<repo>` store.
- Regression coverage for configuration migration, named-library selection, repository installation, discovery, and Windows rollback cleanup.

### Changed

- Treat the central-library root as a flat skill discovery layer and `.repos` as the Git repository storage layer.
- Allow `updates` to resolve the active configured central library when `--central` is omitted.
- Combine one user goal into one reviewable mutation plan and one scope-specific confirmation.

### Breaking

- Runtime operations reject schema v1 configuration instead of silently interpreting it. Run `migrate-config` in dry-run mode and execute it only after reviewing the migration plan.

## [0.1.1] - 2026-08-12

### Fixed

- Normalize cloned skill paths in Windows CI, where temporary directories can be represented by both short and expanded user paths.

### Changed

- Update GitHub-maintained CI actions to their current major versions.

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

[Unreleased]: https://github.com/xhanzo-coder/e8-skill-linker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/xhanzo-coder/e8-skill-linker/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/xhanzo-coder/e8-skill-linker/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/xhanzo-coder/e8-skill-linker/releases/tag/v0.1.0
