# E8 Skill Linker

English | [简体中文](README.zh-CN.md)

Manage existing Agent skills, Git sources and project entry points safely: **one management root, a fixed central library, optional user-named libraries, and an explicit plan/confirmation boundary.**

## What it solves

Inventory skills you already have before choosing what to manage. Share sources across projects without creating a separate physical library for each project. Create an isolated library only when different versions or customizations require it. Preserve complete Git repositories, shared resources and provenance; never guess the origin of an untraceable copied directory.

## Install the manager

Python 3.10+ is required; Git is needed for repository operations. There are no third-party Python runtime dependencies. A user-level installation is recommended for this management skill; business skills remain project-scoped by default.

```bash
npx skills add xhanzo-coder/e8-skill-linker --list
npx skills add xhanzo-coder/e8-skill-linker --skill e8-skill-linker --global --agent codex
```

Use --agent codex claude-code to select both. This installs the manager, not a central library, and does not adopt existing skills. See the [Skills CLI documentation](https://www.skills.sh/docs/cli) for installer options.

## One root, multiple libraries, explicit project references

Choose a root such as E:/SkillsHub once. With no preference, the suggested root is ~/.e8-skill-linker/SkillsHub. A custom path is the root itself; no hidden suffix is appended.

```text
SkillsHub/
├── .skill-linker-registry.json       # Root identity, libraries, registered projects
└── libraries/
    ├── central/                     # Fixed primary library name
    │   ├── .skill-linker-library.json
    │   ├── .skill-linker-lock.json   # Git provenance
    │   ├── .repos/github.com/owner/repo/
    │   └── writer -> .repos/.../skills/writer
    └── <user-chosen-name>/           # Optional, not one per project
```

Project links preserve the central entry, including Windows junctions:

```text
project/.agents/skills/writer
  -> SkillsHub/libraries/central/writer
    -> SkillsHub/libraries/central/.repos/github.com/owner/repo/skills/writer
```

central is reserved. Other names are user-chosen, using lowercase letters, digits and hyphen-separated segments. Each library has independent repository copies and revisions. Different projects can share a library; a project can enable differently named skills from multiple libraries. One project entry name can refer to only one library.

Changing a project's default library does not retarget enabled skills. Updating a shared source affects all its references.

## First use and confirmation

Try: “Use skill-linker to inventory my user-level and current-project skills. Show the list and recommendations first; do not migrate anything.”

1. Read-only inventory of user-level, current-project and configured library entries: names, descriptions, visibility, actual sources, provenance evidence and issues. No full-disk crawl or execution of third-party scripts.
2. Recommend a user-level manager installation after the inventory; reuse an existing copy. Its absence does not block inspection.
3. Reuse a validated v3 root, review a legacy migration, or guide the user to choose a new root with the fixed central library. Unknown nonempty directories are not adopted as empty roots.
4. Recommend binding a new project to central. Existing skills remain untouched unless selected for adoption.
5. Present one concrete plan with absolute paths, selected library, project entries, metadata changes, backups and exclusions. End the turn and wait for confirmation.
6. Execute the confirmed scope, verify actual links and SKILL.md identities, and distinguish new work from existing state.

An ordinary installation request is not approval of unseen targets. Before approval, do not clone (even temporarily), fetch, write configuration or create links. If already fully installed, return a no-change checklist explicitly saying nothing was installed or modified in this run. Third-party setup, dependencies and account connections require separate authorization.

## Identity-based discovery

| File | Responsibility |
| --- | --- |
| User ~/.skill-linker.json | Schema v3, absolute root path and root_id |
| Root .skill-linker-registry.json | Root identity, sole library catalog, project IDs and paths |
| Library .skill-linker-library.json | Root identity, library identity and name |
| Project .skill-linker.json | Root/project identity, default_library and enabled skill→library origins |

A project never overrides the catalog. Bindings contain local-machine identities, not a portable team dependency manifest. Detection validates schema, IDs, containment, registered project paths and actual skill links, not directory names.

Offline roots, missing library markers, invalid defaults and identity conflicts fail explicitly. There is no automatic recreation or fallback to central. Moved/copied projects require explicit project-rebind. Only registered projects are inspected; relocating an entire root or replacing an existing user pointer requires separate review.

## Commands

Run these from this repository; elsewhere use the script's absolute path and the actual --project . directory. Mutating commands preview by default. Add --execute only after reviewing and confirming the plan. --home supports an explicitly chosen user directory, including isolated test fixtures.

```bash
# Read-only inventory
python skills/e8-skill-linker/scripts/skill_manager.py onboard --project .
python skills/e8-skill-linker/scripts/skill_manager.py library-list --project .
python skills/e8-skill-linker/scripts/skill_manager.py project-list --project .

# New root, or connect an existing valid v3 root
python skills/e8-skill-linker/scripts/skill_manager.py root-init --project . --root /absolute/SkillsHub
python skills/e8-skill-linker/scripts/skill_manager.py root-connect --project . --root /absolute/SkillsHub

# After initializing/connecting the root: bind, without enabling every skill
python skills/e8-skill-linker/scripts/skill_manager.py project-bind --project . --library central

# Optional isolation; project-alpha is only an example
python skills/e8-skill-linker/scripts/skill_manager.py library-add --name project-alpha
python skills/e8-skill-linker/scripts/skill_manager.py library-use --project . --name project-alpha

# Install and enable in an already-bound project
python skills/e8-skill-linker/scripts/skill_manager.py install-repo --project . --library central --repo-url https://github.com/example/skills.git --skills writer=skills/writer --enable-project

# Enable an existing source / disable its project entry
python skills/e8-skill-linker/scripts/skill_manager.py link --project . --library central --source /absolute/SkillsHub/libraries/central/writer
python skills/e8-skill-linker/scripts/skill_manager.py unlink --project . --target .agents/skills/writer

# All registered libraries; updates reads cached state unless --execute is approved
python skills/e8-skill-linker/scripts/skill_manager.py check --project . --all-libraries
python skills/e8-skill-linker/scripts/skill_manager.py updates --project . --all-libraries
```

root-connect execution also requires the reviewed --expected-root-id. config is now read-only. Old --scope, --central-base, --activate and global-central override flags were removed. A management root cannot overlap Agent discovery directories.

Use name=. for a repository-root skill, or codex-with-chatgpt=skill when directory and skill names differ. The entry must match frontmatter identity. Registered repositories reuse their local revision; adding entries does not fetch automatically. See the [CLI reference](skills/e8-skill-linker/references/script-commands.md) for move/copy rebinding, multi-Agent hubs, adoption, restore and Git commands.

## Updates and impact

Each library's .skill-linker-lock.json records repository URL, relative location, installed revision, skill subpaths and exposed entries. A nonempty .repos without a valid registry is an error. An installed revision does not establish remote freshness: updates distinguishes local-cache, fetched and fetch-failed.

update validates the registry and worktree, fetches, validates registered skills in the candidate commit, and applies that exact SHA with git merge --ff-only before recording the revision. Dirty worktrees, missing upstreams, detached HEAD, divergence, removed skills or changed identities stop the update. Newly available skills are not enabled automatically. Failures after applying a commit do not automatically reset the user's worktree.

Managed updates and checkouts report registered-project declarations and observed hub references. Inaccessible projects are explicit inspection errors. Unregistered projects and external user-level links are outside that impact graph; absence from the report is not proof of no other references.

## Existing skills and v2 migration

A plain independent skill directory can be selectively adopted as a local snapshot: review dependencies, verify a full content digest, copy and validate, retain an original backup and receipt, and replace the original entry with a link. Preserve its user/project visibility. restore-adoption restores the original directory while retaining the central copy; changed content blocks restoration. Only standard same-name project hub entries are tracked in enabled; other entry scopes remain visible in inventory.

A copied folder may not retain enough evidence to recover its repository or installed revision. Documentation URLs are candidates, not proof; an enclosing business project's remote is not the skill's source. Other installers' lock files are listed for review, not generically interpreted. Arbitrary old Git installations have no one-click conversion.

Schema v2 configurations cannot run directly. Preview an explicit migration:

```bash
python skills/e8-skill-linker/scripts/skill_manager.py migrate-config --root /absolute/NewSkillsHub --main-library <old-primary-name>
```

After approval, add --expected-digest <digest> --execute. The target root must not exist. Migration copies libraries into the new layout, maps the selected old library to central, backs up the user configuration, and preserves originals and old project links. Old project configurations require project-bind --replace-v2 and a separate reviewed unlink/relink plan.

Automatic migration handles v2 user configuration only. Libraries with .skill-linker-local adoption receipts, unregistered nested links, Git worktrees/submodules, special files, overlapping sources or more than 10,000 entries / 256 MiB / 32 levels require separate review. v1 is not supported by this command. Copy failure retains the partial new root for diagnosis, leaving the old libraries and pointer intact; do not blindly retry or delete it. See [layout and migration boundaries](skills/e8-skill-linker/references/bootstrap-and-central-library.md).

## Safety and platforms

- macOS/Linux directory symlinks; Windows can explicitly use --link-type junction. Never silently elevate privileges.
- Never replace a real directory or a link pointing elsewhere. “Delete this skill” means disabling the project entry unless source deletion is explicitly requested.
- Root/project metadata uses a cooperative write lock and stale-state checks. Ordinary write failures attempt rollback; cross-command, forced-termination and power-loss atomicity are not guaranteed.
- Keep project adoption backups out of Git. Manager replacement backups live outside Agent discovery directories.
- Machine-local links and bindings need review on other machines. Passing script tests does not prove every model will respect the conversational confirmation gate.

## Development

```bash
python scripts/validate_skill.py skills/e8-skill-linker
python -m unittest discover -s tests -v
python -m py_compile skills/e8-skill-linker/scripts/skill_manager.py skills/e8-skill-linker/scripts/root_state.py
```

Runtime instructions live in SKILL.md and references/. Deterministic operations are in scripts/skill_manager.py and scripts/root_state.py. Tests cover repository workflows, onboarding/adoption and root/project identity in test_root_state.py. Conversational evidence is separate in [interaction-cases.md](tests/interaction-cases.md); historical replays are not claimed as validation of the new schema.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [MIT License](LICENSE)
