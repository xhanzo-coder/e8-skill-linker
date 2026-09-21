# Security Policy

## Supported Versions

Security fixes are applied to the latest release and the `main` branch.

## Reporting a Vulnerability

Do not open a public issue for a vulnerability. Use the repository's
[private vulnerability reporting](https://github.com/xhanzo-coder/e8-skill-linker/security/advisories/new)
and include:

- The affected command or Agent workflow.
- The operating system and Python version.
- A minimal reproduction using non-sensitive paths and repositories.
- The expected impact and any known mitigation.

Please do not include credentials, access tokens, private repository URLs, or
personal directory contents. The maintainer will acknowledge a complete report
as soon as practical and coordinate disclosure after a fix is available.

## Security Boundaries

E8 Skill Linker manages local paths and invokes Git. It is not a malware scanner
or a sandbox. Review third-party skills before enabling them.

The manager is designed to:

- Dry-run mutating operations unless `--execute` is supplied.
- Restrict project links to the configured central library or project skill hub.
- Reject path-like skill names, repository subpath traversal, and option-like Git refs or repository URLs.
- Refuse to overwrite real directories with links.
- Keep complete Git sources under the selected central library's `.repos` directory and validate planned skill names against `SKILL.md` before exposing them.
- Roll back repositories and links created by a failed transactional installation, including read-only Git objects on Windows.
- Validate `.skill-linker-lock.json` before trusting recorded repository paths or revisions.
- Preserve central sources when a project link is removed.
- Refuse updates for dirty repositories and require an upstream. Inspect registered skill identities in the fetched candidate, fast-forward to that exact commit, then validate entries before recording the new revision.
- Preserve project links through stable central entries, including Windows junctions; compare immediate targets instead of treating flattened links as equivalent.
- Store management-skill replacement backups outside Agent discovery directories.
- Avoid silent privilege elevation on Windows.

The manager may still execute networked Git operations after explicit user
confirmation. A cloned or updated repository can contain malicious instructions
or scripts, so repository trust remains the user's responsibility.
