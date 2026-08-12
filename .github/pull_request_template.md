## Summary

Describe the behavior changed and why.

## Safety impact

Explain any effect on paths, links, junctions, file movement, deletion, Git commands, or confirmation requirements.

## Validation

- [ ] `python -m unittest discover -s tests -v`
- [ ] `python scripts/validate_skill.py skills/e8-skill-linker`
- [ ] `python -m py_compile skills/e8-skill-linker/scripts/skill_manager.py tests/test_skill_manager.py`
- [ ] Documentation matches the implemented behavior
