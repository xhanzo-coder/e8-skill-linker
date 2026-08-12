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
- Reject path-like skill names and option-like Git refs or repository URLs.
- Refuse to overwrite real directories with links.
- Preserve central sources when a project link is removed.
- Refuse Git pulls for dirty repositories by default and require an upstream.
- Avoid silent privilege elevation on Windows.

The manager may still execute networked Git operations after explicit user
confirmation. A cloned or updated repository can contain malicious instructions
or scripts, so repository trust remains the user's responsibility.
