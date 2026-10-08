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

- The central-library root stores discoverable skill sources or entries. The default is `~/.e8-skill-linker/AgentSkills`.
- Complete third-party Git repositories live under `<central>/.repos/<host>/<owner>/<repo>`; root-level skill symlinks or junctions point to skill directories inside them.
- `<central>/.skill-linker-lock.json` records repository sources, current revisions, subpaths, and exposed central skill entries.
- Common macOS/Linux Agent global directories include `~/.agents/skills`, `~/.codex/skills`, and `~/.claude/skills`.
- On Windows, the default central library is `%USERPROFILE%\.e8-skill-linker\AgentSkills`.
- Project-level `.agents/skills`, `.codex/skills`, and `.claude/skills` are entry points for the current project.

Business skills are not installed globally by default. `e8-skill-linker` is a management skill, so it may be installed globally as an exception to make it discoverable in new projects and conversations.

## Requirements and Compatibility

- Python 3.10 or newer; no third-party runtime packages are required.
- Git is required for clone, update, checkout, repository status and local source evidence in `onboard`.
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

1. Run `onboard --project .` to inventory user-level, current-project and configured central entries without writes. Show names, descriptions, visibility, actual sources, provenance evidence, duplicate relationships and issues. Do not crawl other projects or execute third-party scripts.
2. After presenting the inventory, recommend a user-level manager installation if needed. An existing installation is reused; its absence does not block inspection.
3. Recommend reusing a valid library, ask about unregistered candidates, and report invalid configuration/registries. With no library, suggest `personal` at a non-global location or accept an explicitly selected existing custom directory without forcing a move.
4. Let the user choose initialization only or specific adoption items. Existing skills stay untouched by default; creating a library does not migrate them.
5. Present one plan covering manager setup, configuration, selected items, backups, preserved entry scopes and exclusions. End the turn and wait for confirmation before executing selected actions.
6. Adopt plain independent directories as backed-up local snapshots while preserving their user/project entry scopes. Verify and provide recovery receipts; do not pretend unknown snapshots are updateable Git repositories.

Try: “Use skill-linker to inventory my user-level and current-project skills. Show the list and recommendations first; do not migrate anything.”

```bash
python skills/e8-skill-linker/scripts/skill_manager.py onboard --project .
```

`migrate` outputs a plan and content digest. After confirmation, execution also requires `--expected-digest <digest> --dependencies-reviewed --execute`. `restore-adoption --receipt <receipt>` previews restoration; add `--execute` after confirmation. The central copy is retained. See [first use and adoption](skills/e8-skill-linker/references/first-use-and-adoption.md).

Provenance has limits: document URLs are candidates, an enclosing business project's Git remote is not the skill source, and other installers' lock files are currently listed for review rather than parsed generically. A copied directory may not retain enough evidence to recover its repository or installed revision. Converting arbitrary old Git installations to managed repositories still needs a separate review; there is no one-click conversion command.

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

Project-level configuration completely overrides user-level configuration. Schema v2 can register multiple named central libraries, while each effective configuration selects exactly one `active_library`.

Example:

```json
{
  "schema_version": 2,
  "libraries": {
    "personal": {
      "path": "/Users/you/.e8-skill-linker/AgentSkills"
    },
    "work": {
      "path": "/Volumes/Work/.e8-skill-linker/AgentSkills"
    }
  },
  "active_library": "personal",
  "default_mode": "centralize"
}
```

Windows example:

```json
{
  "schema_version": 2,
  "libraries": {
    "personal": {
      "path": "C:\\Users\\you\\.e8-skill-linker\\AgentSkills"
    }
  },
  "active_library": "personal",
  "default_mode": "centralize"
}
```

Run a dry-run first:

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --library personal \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize
```

After confirmation, execute the change:

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --library personal \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize \
  --execute
```

When the user provides a custom parent directory, use `--central-base`. The actual central library becomes `<parent>/.e8-skill-linker/AgentSkills`:

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --library personal \
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

# Show named libraries in user, project, and effective scopes
python3 skills/e8-skill-linker/scripts/skill_manager.py library-list --project .

# Explicitly migrate a v1 config to schema v2 (dry-run first)
python3 skills/e8-skill-linker/scripts/skill_manager.py migrate-config --scope user --library personal

# Add a named work library without replacing the existing configuration
python3 skills/e8-skill-linker/scripts/skill_manager.py library-add \
  --scope user --name work --central-base /Volumes/Work

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

# Preserve a complete third-party repository, expose its skills, and enable them here
python3 skills/e8-skill-linker/scripts/skill_manager.py install-repo \
  --project . \
  --repo-url https://github.com/example/skills.git \
  --skills writer=skills/writer,reviewer=.agents/skills/reviewer \
  --enable-project

# Disable a skill in the current project without deleting its source
python3 skills/e8-skill-linker/scripts/skill_manager.py unlink \
  --target .agents/skills/write-blog

# Check Git repositories in the central library for updates
python3 skills/e8-skill-linker/scripts/skill_manager.py updates --project .
```

`link`, `link-many`, and `migrate` reject sources that are not configured or authorized. Do not point links directly at arbitrary download directories, desktop folders, repository roots, or temporary directories.

## Named Libraries and Repository Updates

Project links preserve a stable central entry on every platform, including Windows junctions:

```text
project/.agents/skills/writer
  -> central/writer
    -> central/.repos/github.com/owner/repository/skills/writer
```

Use `--library work` with `install-repo`, `link`, `link-many`, `check`, `updates`, or `update` to select a library for one command without changing `active_library`. Project configuration still completely overrides user configuration. Each library has independent repository copies and a registry. Switching the default library reports existing project link ownership and leaves those links in place.

Run these commands from this repository; from another directory, use the absolute path to `skill_manager.py`. Mutating examples below assume you have reviewed and approved their scope.

```bash
# Install into work; reuse the same repository when adding another skill later
python3 skills/e8-skill-linker/scripts/skill_manager.py install-repo \
  --library work --repo-url https://github.com/example/skills.git \
  --skills writer=skills/writer --execute

# Enable an already installed skill in another project through its central entry
python3 skills/e8-skill-linker/scripts/skill_manager.py link \
  --project /path/to/project --library work \
  --source /Volumes/Work/.e8-skill-linker/AgentSkills/writer --execute

# Fetch update information for every library in the effective configuration
python3 skills/e8-skill-linker/scripts/skill_manager.py updates --all-libraries --execute

# Apply a reviewed repository update in work
python3 skills/e8-skill-linker/scripts/skill_manager.py update --library work \
  --repo /Volumes/Work/.e8-skill-linker/AgentSkills/.repos/github.com/example/skills --execute

python3 skills/e8-skill-linker/scripts/skill_manager.py check --all-libraries
```

Updates use `.skill-linker-lock.json` as the repository inventory. They do not scan legacy repositories at the central root. A nonempty `.repos` without a registry is an error. The stored revision records the installed commit; it cannot tell you whether GitHub has newer commits without a fetch.

`updates` labels each result `local-cache`, `fetched`, or `fetch-failed`. Only a successful fetch provides fresh remote information. Failed fetches and missing upstream branches are unknown states, not “up to date.” There is no background polling.

`update` fetches once, checks that registered skills still exist with matching identities in the candidate commit, and applies that exact SHA using `git merge --ff-only`. It then validates central entries and records the new revision. Dirty worktrees, detached HEAD, missing upstream, divergence, removed skills, or changed identities stop the update. A rejected candidate leaves the worktree unchanged, although fetched Git metadata remains. If validation or registry writing fails after applying the commit, the command reports failure without automatically resetting the worktree.

Reports distinguish repository changes, directly changed installed skills, added/deleted skill paths, and available unexposed skills. Shared resource changes may affect other skills too. New skills require explicit installation; run `install-repo` again to add them using the existing repository. Root skills use `name=.` and may have a different name from the repository.

Existing project links that point directly into `.repos` are not silently rewritten. Inspect their immediate targets with `check`, then explicitly unlink and relink through the central entry. Replacement backups of the management skill are stored under `~/.e8-skill-linker/backups/e8-skill-linker/`, outside Agent discovery directories.

Repository directory names do not need to match skill names on any platform. For example, `--skills codex-with-chatgpt=skill` exposes a skill from `skill/SKILL.md` as `codex-with-chatgpt`. The entry name must match the frontmatter `name`, and the source path must stay inside the repository. No upstream directory is renamed.

Project roots must already exist. For the current project, obtain the actual working directory from the environment and use `--project .`; do not retype punctuation in paths or continue after a failed directory change. Installation and linking report verified absolute project entry paths, immediate targets and readable skill identities. Central-library validation alone does not prove project installation.

An ordinary installation request follows read-only inspection and planning → end the turn and wait for confirmation → execute and verify. Before confirmation, do not clone (even temporarily), fetch, write configuration, create links, or run third-party scripts; a successful dry-run is not confirmation. If only the project entry is missing, present an enablement plan. If everything requested already exists, provide a checklist explicitly stating that this run only inspected and changed nothing; recommend keeping the existing installation without rerunning a write command. Third-party dependencies and initialization require separate authorization. Existing approval of the same plan, or an explicit user request to skip confirmation within a defined scope, need not be requested again. The CLI flag does not enforce this conversation requirement. See [interaction replay cases](tests/interaction-cases.md) for the separate behavioral checks.

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
└── tests/
    ├── test_skill_manager.py
    ├── test_repository_workflows.py
    ├── test_onboarding.py
    └── interaction-cases.md
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
