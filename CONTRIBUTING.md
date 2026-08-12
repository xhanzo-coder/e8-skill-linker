# Contributing to E8 Skill Linker

Thanks for helping improve skill management across Agent tools.

## Development

Requirements:

- Python 3.10 or newer
- Git
- macOS, Linux, or Windows

The runtime script uses only the Python standard library. Before opening a pull
request, run:

```bash
python -m unittest discover -s tests -v
python scripts/validate_skill.py skills/e8-skill-linker
python -m py_compile skills/e8-skill-linker/scripts/skill_manager.py tests/test_skill_manager.py
```

## Change Guidelines

- Keep `SKILL.md` concise and route detailed workflows through `references/`.
- Keep the English and Chinese README files behaviorally consistent.
- Preserve dry-run defaults and explicit confirmation requirements.
- Add or update tests for path, link, migration, Git, or Windows behavior.
- Do not add silent recovery, destructive overwrite, privilege escalation, or
  credential handling.
- Do not commit local `.agents`, `.codex`, `.claude`, or `.skill-linker.json`
  state.

Bug reports and feature requests should use the repository issue templates.
Security reports must follow [SECURITY.md](SECURITY.md).
