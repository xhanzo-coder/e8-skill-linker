# 118 Skill Linker

[English](README.md) | [简体中文](README.zh-CN.md)

`118-skill-linker` is a management skill for organizing Agent skills. It keeps skill sources in an explicit central library and creates project-level links for the skills each project uses, so you can manage Codex, Claude Code, and other Agent Skills-compatible tools from one place.

It is useful when you need to:

- Reuse the same skills across multiple projects.
- Install, clone, migrate, link, update, or disable skills.
- Distinguish user-level Agent directories, project-level entry points, and central skill sources.
- Maintain customized versions of third-party skills while tracking Git updates or fork status.
- Manage project links with symlinks or junctions on macOS, Linux, and Windows.

## Key Concepts

This repository contains one skill at `skills/118-skill-linker/`:

- `SKILL.md`: Core rules loaded by the Agent after the skill is triggered.
- `references/`: Detailed workflows loaded only when needed.
- `scripts/`: Deterministic scripts for inspection, configuration, linking, and migration.

The central skill library and Agent global directories are different things:

- The central library stores skill sources. The default is `~/.118-skill-linker/AgentSkills`.
- Common macOS/Linux Agent global directories include `~/.agents/skills`, `~/.codex/skills`, and `~/.claude/skills`.
- On Windows, the default central library is `%USERPROFILE%\.118-skill-linker\AgentSkills`.
- Project-level `.agents/skills`, `.codex/skills`, and `.claude/skills` are entry points for the current project.

Business skills are not installed globally by default. `118-skill-linker` is a management skill, so it may be installed globally as an exception to make it discoverable in new projects and conversations.

## Install with npx

`npx skills` is the open Agent Skills ecosystem's installation CLI. It discovers and installs skills with a valid `SKILL.md` from GitHub and other sources. This repository does not need to be published as an npm package.

List the skills discovered in this repository:

```bash
npx skills add xhanzo-coder/118-skill-linker --list
```

Install the skill for Codex in the current project:

```bash
npx skills add xhanzo-coder/118-skill-linker \
  --skill 118-skill-linker \
  --agent codex
```

Install the management skill globally for Codex:

```bash
npx skills add xhanzo-coder/118-skill-linker \
  --skill 118-skill-linker \
  --global \
  --agent codex
```

Install it globally for both Codex and Claude Code:

```bash
npx skills add xhanzo-coder/118-skill-linker \
  --skill 118-skill-linker \
  --global \
  --agent codex \
  --agent claude-code
```

After installation, the first use of `118-skill-linker` still checks the central library configuration and asks whether bootstrapping is needed. `npx skills add` installs the management skill; it does not automatically create or choose `~/.118-skill-linker/AgentSkills`.

Update or remove a globally installed copy:

```bash
npx skills update --global 118-skill-linker
npx skills remove --global --agent codex 118-skill-linker
```

See the [Skills CLI documentation](https://www.skills.sh/docs/cli) for more source formats and options.

## First Use

When triggered for the first time, the skill follows this sequence:

1. Check whether `118-skill-linker` is installed in a user-level Agent skills directory.
2. Read the project-level and user-level `.skill-linker.json` files.
3. If no configuration exists, recommend a non-global central library: `~/.118-skill-linker/AgentSkills` on macOS/Linux or `%USERPROFILE%\.118-skill-linker\AgentSkills` on Windows.
4. Accept a custom parent directory and derive `<parent>/.118-skill-linker/AgentSkills` beneath it.
5. Inspect project-level and user-level skills in read-only mode and show sources, targets, and impacts separately.
6. Present a plan and wait for confirmation before configuring, migrating, syncing, linking, removing, cloning, or running Git updates.

By default, `~/.agents/skills`, `~/.codex/skills`, and `~/.claude/skills` are not treated as the central library. If a user chooses one of these global directories, the skill must explain that the skills may become visible to every project and request explicit confirmation.

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
  "central_skills_dir": "/Users/you/.118-skill-linker/AgentSkills",
  "default_mode": "centralize"
}
```

Windows example:

```json
{
  "central_skills_dir": "C:\\Users\\you\\.118-skill-linker\\AgentSkills",
  "default_mode": "centralize"
}
```

Run a dry-run first:

```bash
python3 skills/118-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central ~/.118-skill-linker/AgentSkills \
  --mode centralize
```

After confirmation, execute the change:

```bash
python3 skills/118-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central ~/.118-skill-linker/AgentSkills \
  --mode centralize \
  --execute
```

When the user provides a custom parent directory, use `--central-base`. The actual central library becomes `<parent>/.118-skill-linker/AgentSkills`:

```bash
python3 skills/118-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central-base "/Users/name/Desktop/WorkSpace" \
  --mode centralize
```

## Common Commands

The commands below inspect or dry-run by default. Add `--execute` only after the user has reviewed and confirmed the plan.

```bash
# Inspect project, user-level directories, and link status
python3 skills/118-skill-linker/scripts/skill_manager.py inspect --project .

# Show the effective configuration
python3 skills/118-skill-linker/scripts/skill_manager.py config --project .

# Check broken links and structural problems
python3 skills/118-skill-linker/scripts/skill_manager.py check --project .

# Initialize project-level entry points
python3 skills/118-skill-linker/scripts/skill_manager.py init \
  --project . \
  --agents claude,codex

# Link one skill from the central library
python3 skills/118-skill-linker/scripts/skill_manager.py link \
  --project . \
  --source ~/.118-skill-linker/AgentSkills/write-blog

# Link multiple skills
python3 skills/118-skill-linker/scripts/skill_manager.py link-many \
  --project . \
  --sources ~/.118-skill-linker/AgentSkills/a,~/.118-skill-linker/AgentSkills/b

# Disable a skill in the current project without deleting its source
python3 skills/118-skill-linker/scripts/skill_manager.py unlink \
  --target .agents/skills/write-blog

# Check Git repositories in the central library for updates
python3 skills/118-skill-linker/scripts/skill_manager.py updates \
  --central ~/.118-skill-linker/AgentSkills
```

`link`, `link-many`, and `migrate` reject sources that are not configured or authorized. Do not point links directly at arbitrary download directories, desktop folders, repository roots, or temporary directories.

## Windows

Windows can use directory symlinks or junctions:

```powershell
python skills\118-skill-linker\scripts\skill_manager.py init `
  --project . `
  --agents claude,codex `
  --link-type junction

python skills\118-skill-linker\scripts\skill_manager.py link `
  --project . `
  --source C:\Users\you\.118-skill-linker\AgentSkills\write-blog `
  --link-type junction
```

Creating a symlink may require Developer Mode or an elevated terminal. An Agent may detect and explain permission errors, but it must not silently elevate privileges, bypass UAC, or enter an administrator password.

## Safety Behavior

- Start with a read-only inspection or dry-run by default.
- Present a plan and wait for confirmation before configuring the central library, migrating, syncing, cloning, updating, checking out, deleting, or creating links.
- Never overwrite an existing real directory with a link.
- Interpret “delete this skill” as disabling it in the current project unless the user explicitly asks to delete the source directory.
- Editing a skill through a link changes the central source and affects every project pointing to it.
- Do not pull over or discard local changes in a third-party skill. Discuss fork and Git ownership before long-term maintenance.

## Repository Layout

```text
118-skill-linker/
├── README.md
├── README.zh-CN.md
├── skills/
│   └── 118-skill-linker/
│       ├── SKILL.md
│       ├── agents/
│       │   └── openai.yaml
│       ├── references/
│       └── scripts/
└── .gitignore
```

## Development and Validation

This project follows the [Agent Skills Specification](https://agentskills.io/specification). After changing the skill, run at least:

```bash
skills-ref validate skills/118-skill-linker
python3 -m py_compile skills/118-skill-linker/scripts/skill_manager.py
```

Detailed Agent workflows belong in `skills/118-skill-linker/references/`. README files are human-facing documentation and should not be the only source of Agent runtime rules.

## License

This repository does not currently declare a specific license. Before distributing it as an open-source project, choose a license and add a root-level `LICENSE` file. A public repository alone does not grant permission to freely copy, modify, or redistribute the contents.
