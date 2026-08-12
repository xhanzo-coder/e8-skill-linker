# E8 Skill Linker

[English](README.md) | [简体中文](README.zh-CN.md)

[![CI](https://github.com/xhanzo-coder/e8-skill-linker/actions/workflows/ci.yml/badge.svg)](https://github.com/xhanzo-coder/e8-skill-linker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-111827.svg)](https://agentskills.io/)

`e8-skill-linker` is a management skill for organizing Agent skills. It keeps skill sources in an explicit central library and creates project-level links for the skills each project uses, so you can manage Codex, Claude Code, and other Agent Skills-compatible tools from one place.

It is useful when you need to:

- Reuse the same skills across multiple projects.
- Install, clone, migrate, link, update, or disable skills.
- Distinguish user-level Agent directories, project-level entry points, and central skill sources.
- Maintain customized versions of third-party skills while tracking Git updates or fork status.
- Manage project links with symlinks or junctions on macOS, Linux, and Windows.

## Key Concepts

This repository contains one skill at `skills/e8-skill-linker/`:

- `SKILL.md`: Core rules loaded by the Agent after the skill is triggered.
- `references/`: Detailed workflows loaded only when needed.
- `scripts/`: Deterministic scripts for inspection, configuration, linking, and migration.

The central skill library and Agent global directories are different things:

- The central library stores skill sources. The default is `~/.e8-skill-linker/AgentSkills`.
- Common macOS/Linux Agent global directories include `~/.agents/skills`, `~/.codex/skills`, and `~/.claude/skills`.
- On Windows, the default central library is `%USERPROFILE%\.e8-skill-linker\AgentSkills`.
- Project-level `.agents/skills`, `.codex/skills`, and `.claude/skills` are entry points for the current project.

Business skills are not installed globally by default. `e8-skill-linker` is a management skill, so it may be installed globally as an exception to make it discoverable in new projects and conversations.

## Requirements and Compatibility

- Python 3.10 or newer; no third-party runtime packages are required.
- Git is required only for clone, update, checkout, and repository status commands.
- macOS and Linux use directory symlinks.
- Windows supports directory symlinks and junctions. Symlinks may require Developer Mode or an elevated terminal; junctions usually do not.
- Codex, Claude Code, and other tools that discover Agent Skills from compatible project directories can share the same project skill hub.

## Install with npx

`npx skills` is the open Agent Skills ecosystem's installation CLI. It discovers and installs skills with a valid `SKILL.md` from GitHub and other sources. This repository does not need to be published as an npm package.

List the skills discovered in this repository:

```bash
npx skills add xhanzo-coder/e8-skill-linker --list
```

Install the skill for Codex in the current project:

```bash
npx skills add xhanzo-coder/e8-skill-linker \
  --skill e8-skill-linker \
  --agent codex
```

Install the management skill globally for Codex:

```bash
npx skills add xhanzo-coder/e8-skill-linker \
  --skill e8-skill-linker \
  --global \
  --agent codex
```

Install it globally for both Codex and Claude Code:

```bash
npx skills add xhanzo-coder/e8-skill-linker \
  --skill e8-skill-linker \
  --global \
  --agent codex claude-code
```

After installation, the first use of `e8-skill-linker` still checks the central library configuration and asks whether bootstrapping is needed. `npx skills add` installs the management skill; it does not automatically create or choose `~/.e8-skill-linker/AgentSkills`.

Update or remove a globally installed copy:

```bash
npx skills update e8-skill-linker --global
npx skills remove e8-skill-linker --global --agent codex
```

See the [Skills CLI documentation](https://www.skills.sh/docs/cli) for more source formats and options.

## First Use

When triggered for the first time, the skill follows this sequence:

1. Check whether `e8-skill-linker` is installed in a user-level Agent skills directory.
2. Read the project-level and user-level `.skill-linker.json` files.
3. If no configuration exists, recommend a non-global central library: `~/.e8-skill-linker/AgentSkills` on macOS/Linux or `%USERPROFILE%\.e8-skill-linker\AgentSkills` on Windows.
4. Accept a custom parent directory and derive `<parent>/.e8-skill-linker/AgentSkills` beneath it.
5. Inspect project-level and user-level skills in read-only mode and show sources, targets, and impacts separately.
6. Present a plan and wait for confirmation before configuring, migrating, syncing, linking, removing, cloning, or running Git updates.

By default, `~/.agents/skills`, `~/.codex/skills`, and `~/.claude/skills` are not treated as the central library. If a user chooses one of these global directories, the skill must explain that the skills may become visible to every project and request explicit confirmation.

The CLI enforces these exceptional choices: use `--allow-global-central` only after confirming an Agent global directory, and `--allow-non-namespaced-central` only after confirming a final central path that intentionally omits `.e8-skill-linker/AgentSkills`.

An Agent global directory normally triggers both warnings, so execution requires both flags after the user has confirmed both consequences.

## Configure the Central Library

The user-level configuration file is:

```text
~/.skill-linker.json
```

The project-level configuration file is:

```text
<project-root>/.skill-linker.json
```

Project-level configuration takes precedence over user-level configuration. For personal use, configure one user-level central library. Use project-level configuration for team-shared, customer-isolated, or test-specific libraries.

Example:

```json
{
  "central_skills_dir": "/Users/you/.e8-skill-linker/AgentSkills",
  "default_mode": "centralize"
}
```

Windows example:

```json
{
  "central_skills_dir": "C:\\Users\\you\\.e8-skill-linker\\AgentSkills",
  "default_mode": "centralize"
}
```

Run a dry-run first:

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize
```

After confirmation, execute the change:

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize \
  --execute
```

When the user provides a custom parent directory, use `--central-base`. The actual central library becomes `<parent>/.e8-skill-linker/AgentSkills`:

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central-base "/Users/name/Desktop/WorkSpace" \
  --mode centralize
```

## Common Commands

The commands below inspect or dry-run by default. Add `--execute` only after the user has reviewed and confirmed the plan.

```bash
# Inspect project, user-level directories, and link status
python3 skills/e8-skill-linker/scripts/skill_manager.py inspect --project .

# Show the effective configuration
python3 skills/e8-skill-linker/scripts/skill_manager.py config --project .

# Check broken links and structural problems
python3 skills/e8-skill-linker/scripts/skill_manager.py check --project .

# Also check user-level Agent directories and the configured central library
python3 skills/e8-skill-linker/scripts/skill_manager.py check \
  --project . \
  --include-user \
  --include-central

# Initialize project-level entry points
python3 skills/e8-skill-linker/scripts/skill_manager.py init \
  --project . \
  --agents claude,codex

# Link one skill from the central library
python3 skills/e8-skill-linker/scripts/skill_manager.py link \
  --project . \
  --source ~/.e8-skill-linker/AgentSkills/write-blog

# Link multiple skills
python3 skills/e8-skill-linker/scripts/skill_manager.py link-many \
  --project . \
  --sources ~/.e8-skill-linker/AgentSkills/a,~/.e8-skill-linker/AgentSkills/b

# Disable a skill in the current project without deleting its source
python3 skills/e8-skill-linker/scripts/skill_manager.py unlink \
  --target .agents/skills/write-blog

# Check Git repositories in the central library for updates
python3 skills/e8-skill-linker/scripts/skill_manager.py updates \
  --central ~/.e8-skill-linker/AgentSkills
```

`link`, `link-many`, and `migrate` reject sources that are not configured or authorized. Do not point links directly at arbitrary download directories, desktop folders, repository roots, or temporary directories.

## Windows

Windows can use directory symlinks or junctions:

```powershell
python skills\e8-skill-linker\scripts\skill_manager.py init `
  --project . `
  --agents claude,codex `
  --link-type junction

python skills\e8-skill-linker\scripts\skill_manager.py link `
  --project . `
  --source C:\Users\you\.e8-skill-linker\AgentSkills\write-blog `
  --link-type junction
```

Creating a symlink may require Developer Mode or an elevated terminal. An Agent may detect and explain permission errors, but it must not silently elevate privileges, bypass UAC, or enter an administrator password.

## Safety Behavior

- Start with a read-only inspection or dry-run by default.
- Present a plan and wait for confirmation before configuring the central library, migrating, syncing, cloning, updating, checking out, deleting, or creating links.
- Never overwrite an existing real directory with a link.
- Preflight every target before a batch link or multi-Agent initialization begins.
- Back up an existing global `e8-skill-linker` copy before an explicitly confirmed replacement.
- Interpret “delete this skill” as disabling it in the current project unless the user explicitly asks to delete the source directory.
- Editing a skill through a link changes the central source and affects every project pointing to it.
- Reject path-traversal names and links outside authorized roots.
- Do not pull over local changes, pull without an upstream, or use a non-fast-forward Git update. Discuss fork and Git ownership before long-term maintenance.

See [SECURITY.md](SECURITY.md) for the trust model and private vulnerability reporting process.

## Repository Layout

```text
e8-skill-linker/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/ci.yml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── README.zh-CN.md
├── SECURITY.md
├── scripts/validate_skill.py
├── skills/
│   └── e8-skill-linker/
│       ├── SKILL.md
│       ├── agents/
│       │   └── openai.yaml
│       ├── references/
│       └── scripts/
└── tests/test_skill_manager.py
```

## Development and Validation

This project follows the [Agent Skills Specification](https://agentskills.io/specification). After changing the skill, run at least:

```bash
python3 scripts/validate_skill.py skills/e8-skill-linker
python3 -m unittest discover -s tests -v
python3 -m py_compile skills/e8-skill-linker/scripts/skill_manager.py tests/test_skill_manager.py
```

CI runs validation and tests on Ubuntu, macOS, and Windows with Python 3.10 and 3.13. Detailed Agent workflows belong in `skills/e8-skill-linker/references/`; README files are human-facing documentation and are not the Agent's runtime rules.

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), report security issues through [private vulnerability reporting](SECURITY.md), and review release changes in [CHANGELOG.md](CHANGELOG.md).

## License

Released under the [MIT License](LICENSE).
