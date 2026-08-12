#!/usr/bin/env python3
"""Validate the repository's Agent Skill without third-party dependencies."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_REFERENCES = {
    "bootstrap-and-central-library.md",
    "git-update-and-fork.md",
    "link-sync-and-removal.md",
    "output-and-confirmation.md",
    "script-commands.md",
    "windows-links.md",
}


def parse_frontmatter(skill_file: Path) -> dict[str, str]:
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md 必须以 YAML frontmatter 开始")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter 缺少结束分隔符") from exc
    data = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"无法解析 frontmatter 行: {line}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def validate(skill_dir: Path) -> None:
    if not skill_dir.is_dir():
        raise ValueError(f"skill 目录不存在: {skill_dir}")
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(f"缺少 SKILL.md: {skill_file}")
    metadata = parse_frontmatter(skill_file)
    if set(metadata) != {"name", "description"}:
        raise ValueError("SKILL.md frontmatter 只能包含 name 和 description")
    name = metadata["name"]
    if name != skill_dir.name:
        raise ValueError(f"skill 名称与目录名不一致: {name} != {skill_dir.name}")
    if len(name) > 64 or not NAME_PATTERN.fullmatch(name):
        raise ValueError(f"skill 名称格式无效: {name}")
    if not metadata["description"]:
        raise ValueError("skill description 不能为空")
    references = skill_dir / "references"
    missing_references = REQUIRED_REFERENCES.difference(path.name for path in references.glob("*.md"))
    if missing_references:
        raise ValueError(f"缺少 reference 文件: {sorted(missing_references)}")
    script = skill_dir / "scripts" / "skill_manager.py"
    if not script.is_file():
        raise ValueError(f"缺少管理脚本: {script}")
    agent_metadata = skill_dir / "agents" / "openai.yaml"
    if not agent_metadata.is_file():
        raise ValueError(f"缺少 Agent UI 元数据: {agent_metadata}")
    prompt_text = agent_metadata.read_text(encoding="utf-8")
    if "$e8-skill-linker" not in prompt_text:
        raise ValueError("agents/openai.yaml 的 default_prompt 必须显式引用 $e8-skill-linker")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an E8 Skill Linker skill directory.")
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args()
    validate(args.skill_dir)
    print(f"Skill is valid: {args.skill_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
