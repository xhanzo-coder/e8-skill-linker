# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### First-use onboarding

- Add read-only `onboard` inventories with descriptions, visibility scopes, bounded content comparisons, local provenance evidence and explicit unknown/invalid states.
- Separate manager setup, central-library selection and optional adoption; preserve existing global/project visibility and never infer provenance from an enclosing business repository.
- Replace unbacked directory migration with digest-checked local snapshot adoption, original backups, local receipts and `restore-adoption`. Migration execution now requires `--expected-digest` and `--dependencies-reviewed` in addition to user confirmation.
- Keep failed copies on the central volume during rollback; reject discovery-directory central targets and support BOM-encoded skill metadata without rewriting its bytes.
- Document limits: external installer lock formats and arbitrary Git adoption require review; forced-process termination recovery and full runtime dependency verification are not automatic.

### Interaction

- Route installation requests through inspection/plan, a user-confirmation turn boundary, and execution/verification; prohibit preparatory clones and third-party setup before authorization.
- Distinguish fresh installation, project-only enablement, and an already-installed no-change checklist. Report existing state separately from work performed in this run.

### Added

- Per-command `--library` selection for installation, linking, checks and updates; `--all-libraries` for checks and update discovery.
- Registry-driven update reports with cache/fetch freshness, changed files, affected installed skills and available unexposed skills.
- Pre-update validation of registered skills in the candidate commit, followed by exact-commit fast-forward and post-update verification.
- Repository reuse for adding skills and enabling existing skills in another project, with rollback limited to new entries.
- Local Git integration tests for multiple-library isolation, update failures and junction retargeting.

### Fixed

- Reject missing project roots before installation, linking, initialization, migration or project configuration can create unintended directories.
- Verify and report project entry paths, immediate targets and readable skill identities after installation/linking.
- Clarify the default plan/wait/confirm interaction and distinguish successful dry-runs from user approval; add behavioral replay cases separate from script tests.
- Accept explicit skill mappings to differently named repository subdirectories while retaining frontmatter identity and path containment checks.
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
