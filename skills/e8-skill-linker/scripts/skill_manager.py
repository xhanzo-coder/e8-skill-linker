#!/usr/bin/env python3
"""检查并管理项目级 Agent skill 软链接。"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


PROJECT_SKILL_DIRS = [".agents/skills", ".codex/skills", ".claude/skills"]
USER_SKILL_DIRS = ["~/.agents/skills", "~/.codex/skills", "~/.claude/skills"]
DEFAULT_CENTRAL_DIR = "~/.e8-skill-linker/AgentSkills"
EXTRA_NON_GLOBAL_CENTRAL_DIRS = ["~/Skills"]
CENTRAL_NAMESPACE = Path(".e8-skill-linker") / "AgentSkills"
CONFIG_FILENAME = ".skill-linker.json"
VALID_DEFAULT_MODES = {"ask", "centralize", "project-local"}
IS_WINDOWS = platform.system() == "Windows"


def expand(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def expand_with_home(path: str | Path, home: Path) -> Path:
    raw = str(path)
    if raw == "~" or raw.startswith("~/"):
        raw = raw.replace("~", str(home), 1)
    return Path(raw).expanduser().resolve(strict=False)


def expand_preserve_link(path: str | Path) -> Path:
    return Path(path).expanduser()


def classify(path: Path, include_entries: bool = False) -> dict:
    item = {
        "path": str(path),
        "exists": path.exists(),
        "is_symlink": path.is_symlink(),
        "is_junction": is_junction(path),
        "is_dir": path.is_dir(),
        "target": None,
        "broken": False,
        "has_skill_md": False,
        "entries": [],
    }
    if path.is_symlink():
        raw_target = os.readlink(path)
        target = Path(raw_target)
        if not target.is_absolute():
            target = path.parent / target
        item["target"] = str(target.resolve(strict=False))
        item["broken"] = not target.exists()
    if path.exists() and path.is_dir():
        item["has_skill_md"] = (path / "SKILL.md").exists()
        if include_entries:
            item["entries"] = scan_skill_entries(path)
    return item


def is_junction(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    if checker is None:
        return False
    try:
        return bool(checker())
    except OSError:
        return False


def scan_skill_entries(directory: Path) -> list[dict]:
    entries: list[dict] = []
    try:
        children = sorted(directory.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        return [{"name": "<错误>", "error": str(exc)}]
    for child in children:
        if child.name.startswith("."):
            continue
        entry = classify(child, include_entries=False)
        entry["name"] = child.name
        entries.append(entry)
    return entries


def config_paths(project: Path, home: Path) -> dict[str, str]:
    return {
        "project": str(project / CONFIG_FILENAME),
        "user": str(home / CONFIG_FILENAME),
    }


def read_config_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("配置文件顶层必须是 JSON object")
    return data


def default_central_dir(home: Path) -> Path:
    return Path(DEFAULT_CENTRAL_DIR.replace("~", str(home), 1)).expanduser()


def central_from_base(base: Path) -> Path:
    return base / CENTRAL_NAMESPACE


def has_central_namespace(path: Path) -> bool:
    parts = path.parts
    return len(parts) >= 2 and parts[-2:] == CENTRAL_NAMESPACE.parts


def user_skill_paths(home: Path) -> list[Path]:
    return [Path(raw.replace("~", str(home), 1)).expanduser().resolve(strict=False) for raw in USER_SKILL_DIRS]


def is_global_agent_dir(path: Path, home: Path) -> bool:
    probe = path.expanduser().resolve(strict=False)
    return any(probe == candidate for candidate in user_skill_paths(home))


def global_dir_warning(path: Path, home: Path) -> str | None:
    if not is_global_agent_dir(path, home):
        return None
    return (
        "该路径是 Agent 全局 skills 目录。把中央库放在这里可能让其中的 skills 对所有项目全局可见；"
        "如果只是集中存放 skill 原件，推荐使用 ~/.e8-skill-linker/AgentSkills。"
    )


def namespace_warning(path: Path) -> str | None:
    if has_central_namespace(path):
        return None
    return (
        "该 central 路径没有包含 .e8-skill-linker/AgentSkills 命名空间。"
        "如果用户给的是想放置中央库的父目录，请使用 --central-base，让脚本自动派生 <父目录>/.e8-skill-linker/AgentSkills。"
    )


def normalize_config(path: Path, scope: str, data: dict, home: Path) -> dict:
    mode = data.get("default_mode", "ask")
    if mode not in VALID_DEFAULT_MODES:
        raise ValueError(f"default_mode 必须是 {sorted(VALID_DEFAULT_MODES)} 之一")
    central_raw = data.get("central_skills_dir")
    central_path = None
    central_exists = False
    if central_raw:
        central = expand_with_home(str(central_raw), home)
        if not central.is_absolute():
            central = path.parent / central
        central_path = str(central.resolve(strict=False))
        central_exists = central.exists() and central.is_dir()
        warning = global_dir_warning(central, home)
    else:
        warning = None
    return {
        "source": scope,
        "path": str(path),
        "central_skills_dir": central_path,
        "central_exists": central_exists,
        "central_is_global_agent_dir": bool(warning),
        "warning": warning,
        "default_mode": mode,
    }


def load_effective_config(project: Path, home: Path) -> dict:
    paths = config_paths(project, home)
    for scope, raw_path in (("project", paths["project"]), ("user", paths["user"])):
        path = Path(raw_path)
        try:
            data = read_config_file(path)
        except ValueError as exc:
            return {
                "source": "error",
                "path": str(path),
                "error": str(exc),
                "search_paths": paths,
            }
        if data is not None:
            try:
                config = normalize_config(path, scope, data, home)
            except ValueError as exc:
                return {
                    "source": "error",
                    "path": str(path),
                    "error": str(exc),
                    "search_paths": paths,
                }
            config["search_paths"] = paths
            return config
    return {
        "source": None,
        "path": None,
        "central_skills_dir": None,
        "central_exists": False,
        "default_mode": "ask",
        "search_paths": paths,
    }


def global_agent_dirs(home: Path) -> list[str]:
    return [str(candidate) for candidate in user_skill_paths(home) if candidate.exists()]


def candidate_central_dirs(home: Path, configured: str | None = None) -> list[str]:
    candidates: list[Path] = []
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            candidates.append(configured_path)
    github = home / "GitHub"
    if github.exists():
        for repo in sorted(github.iterdir(), key=lambda p: p.name):
            for suffix in ("skills", ".agents/skills"):
                candidate = repo / suffix
                if candidate.exists():
                    candidates.append(candidate)
    for raw in [DEFAULT_CENTRAL_DIR, *EXTRA_NON_GLOBAL_CENTRAL_DIRS]:
        candidate = Path(raw.replace("~", str(home), 1)).expanduser()
        if candidate.exists():
            candidates.append(candidate)
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def collect_duplicate_names(groups: Iterable[dict]) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for group in groups:
        for entry in group.get("entries", []):
            name = entry.get("name")
            if name and not name.startswith("<"):
                seen.setdefault(name, []).append(entry["path"])
    return {name: paths for name, paths in seen.items() if len(paths) > 1}


def inspect(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    config = load_effective_config(project, home)
    project_dirs = [classify(project / rel, include_entries=True) for rel in PROJECT_SKILL_DIRS]
    user_dirs = [classify(expand(rel.replace("~", str(home), 1)), include_entries=True) for rel in USER_SKILL_DIRS]
    report = {
        "project": str(project),
        "config": config,
        "project_skill_dirs": project_dirs,
        "user_skill_dirs": user_dirs,
        "global_agent_dirs": global_agent_dirs(home),
        "recommended_default_central_dir": str(default_central_dir(home).resolve(strict=False)),
        "central_candidates": candidate_central_dirs(home, config.get("central_skills_dir")),
        "duplicates": collect_duplicate_names(project_dirs + user_dirs),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def config(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    if args.central and args.central_base:
        raise SystemExit("不能同时提供 --central 和 --central-base")
    if not args.central and not args.central_base:
        print(json.dumps(load_effective_config(project, home), ensure_ascii=False, indent=2))
        return 0

    central_base = expand_with_home(args.central_base, home) if args.central_base else None
    central = central_from_base(central_base) if central_base else expand_with_home(args.central, home)
    target = project / CONFIG_FILENAME if args.scope == "project" else home / CONFIG_FILENAME
    data = {
        "central_skills_dir": str(central),
        "default_mode": args.mode,
    }
    warning = global_dir_warning(central, home)
    warnings = [item for item in (warning, None if args.central_base else namespace_warning(central)) if item]
    plan = {
        "write_config": str(target),
        "scope": args.scope,
        "central_base_dir": str(central_base) if central_base else None,
        "central_namespace": str(CENTRAL_NAMESPACE),
        "config": data,
        "will_create_config_parent": not target.parent.exists(),
        "will_create_central_dir": not central.exists(),
        "central_is_global_agent_dir": bool(warning),
        "warnings": warnings,
        "recommended_default_central_dir": str(default_central_dir(home).resolve(strict=False)),
    }
    print(json.dumps({"planned_config": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 写入配置文件")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    central.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written_config": str(target)}, ensure_ascii=False, indent=2))
    return 0


def ensure_project_hub(project: Path, execute: bool) -> None:
    hub = project / ".agents" / "skills"
    if hub.exists():
        print(f"已存在: {hub}")
        return
    print(f"将创建目录: {hub}")
    if execute:
        hub.mkdir(parents=True, exist_ok=True)


def resolve_link_target(link: Path, target: Path) -> Path:
    if target.is_absolute():
        return target.resolve(strict=False)
    return (link.parent / target).resolve(strict=False)


def is_path_inside(path: Path, root: Path) -> bool:
    probe = path.resolve(strict=False)
    base = root.resolve(strict=False)
    return probe == base or base in probe.parents


def configured_central(project: Path, home: Path) -> Path:
    config = load_effective_config(project, home)
    if config.get("source") == "error":
        raise SystemExit(f"中央库配置错误: {config['error']}")
    central_raw = config.get("central_skills_dir")
    if not central_raw:
        raise SystemExit("未配置 central_skills_dir；拒绝创建指向未授权目录的软链接")
    central = expand_with_home(central_raw, home)
    if not central.exists() or not central.is_dir():
        raise SystemExit(f"已配置中央库不存在或不是目录: {central}")
    return central


def require_allowed_link_target(link: Path, target: Path, allowed_roots: Iterable[Path]) -> None:
    target_abs = resolve_link_target(link, target)
    roots = list(allowed_roots)
    if any(is_path_inside(target_abs, root) for root in roots):
        return
    allowed = [str(root.resolve(strict=False)) for root in roots]
    raise SystemExit(
        "拒绝创建指向未授权目录的软链接。"
        f" link={link} target={target_abs} allowed_roots={json.dumps(allowed, ensure_ascii=False)}"
    )


def create_windows_junction(link: Path, target: Path) -> None:
    target_abs = resolve_link_target(link, target)
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target_abs)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or result.stdout.strip())


def windows_link_help(link: Path, target: Path, error: OSError) -> str:
    target_abs = resolve_link_target(link, target)
    return (
        f"Windows 创建软链接失败: {error}\n"
        "可选处理方式：\n"
        "1. 开启 Windows Developer Mode 后重试；\n"
        "2. 用管理员权限运行终端后重试；\n"
        "3. 对目录 skill 改用 junction，例如：\n"
        f"   mklink /J \"{link}\" \"{target_abs}\"\n"
        "不要让 Agent 静默提权或自动绕过 UAC；需要用户确认并完成系统权限步骤。"
    )


def create_symlink(
    link: Path,
    target: Path,
    execute: bool,
    link_type: str = "auto",
    allowed_roots: Iterable[Path] | None = None,
) -> None:
    if link_type == "junction" and not IS_WINDOWS:
        raise SystemExit("junction 仅适用于 Windows；macOS/Linux 请使用 auto 或 symlink")
    if allowed_roots is not None:
        require_allowed_link_target(link, target, allowed_roots)
    if link.exists() or link.is_symlink():
        current = classify(link)
        print(f"跳过已存在路径: {link} ({json.dumps(current, ensure_ascii=False)})")
        return
    planned_type = "junction" if IS_WINDOWS and link_type == "junction" else "软链接"
    print(f"将创建{planned_type}: {link} -> {target}")
    if execute:
        link.parent.mkdir(parents=True, exist_ok=True)
        if IS_WINDOWS and link_type == "junction":
            create_windows_junction(link, target)
            return
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError as exc:
            if IS_WINDOWS and link_type == "auto":
                try:
                    create_windows_junction(link, target)
                    print("Windows symlink 权限不足或不可用，已改用 junction。")
                    return
                except OSError as junction_exc:
                    raise SystemExit(windows_link_help(link, target, junction_exc)) from junction_exc
            if IS_WINDOWS:
                raise SystemExit(windows_link_help(link, target, exc)) from exc
            raise


def skill_dirs_in_repo(repo: Path) -> list[str]:
    candidates: list[Path] = []
    if (repo / "SKILL.md").exists():
        candidates.append(repo)
    for base in (repo / "skills", repo / ".agents" / "skills"):
        if base.exists() and base.is_dir():
            for child in sorted(base.iterdir(), key=lambda p: p.name):
                if child.is_dir() and (child / "SKILL.md").exists():
                    candidates.append(child)
    return [str(path.resolve(strict=False)) for path in candidates]


def user_global_skill_dir(home: Path, agent: str) -> Path:
    if agent == "agents":
        return home / ".agents" / "skills"
    if agent == "codex":
        return home / ".codex" / "skills"
    if agent == "claude":
        return home / ".claude" / "skills"
    raise SystemExit(f"未知 Agent: {agent}")


def install_self(args: argparse.Namespace) -> int:
    home = expand(args.home)
    source = expand(args.source) if args.source else Path(__file__).resolve(strict=False).parents[1]
    if not source.exists() or not source.is_dir() or not (source / "SKILL.md").exists():
        raise SystemExit(f"source 必须是包含 SKILL.md 的 e8-skill-linker 目录: {source}")
    agents = parse_agents(args.agents)
    primary = user_global_skill_dir(home, "agents") / "e8-skill-linker"
    plan = {
        "source": str(source),
        "install_primary": str(primary),
        "mode": args.mode,
        "agent_entries": [],
        "will_overwrite": False,
        "note": "e8-skill-linker 是管理型 skill，可作为例外安装到用户级全局目录；业务型 skills 不应因此默认全局安装。",
    }
    if primary.exists() or primary.is_symlink():
        plan["existing_primary"] = classify(primary)
        if not args.replace:
            print(json.dumps({"planned_install_self": plan}, ensure_ascii=False, indent=2))
            raise SystemExit("全局 e8-skill-linker 已存在；默认不覆盖。确认替换时传入 --replace")
        plan["will_overwrite"] = True
    for agent in agents:
        entry = user_global_skill_dir(home, agent) / "e8-skill-linker"
        target = primary if agent != "agents" else source
        plan["agent_entries"].append({"agent": agent, "path": str(entry), "target": str(target)})
    print(json.dumps({"planned_install_self": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 安装 e8-skill-linker")
        return 0
    if primary.exists() or primary.is_symlink():
        if primary.is_symlink() or primary.is_file():
            primary.unlink()
        elif primary.is_dir():
            shutil.rmtree(primary)
    primary.parent.mkdir(parents=True, exist_ok=True)
    if args.mode == "copy":
        shutil.copytree(source, primary, symlinks=True)
    else:
        create_symlink(primary, source, True, args.link_type)
    for agent in agents:
        if agent == "agents":
            continue
        entry = user_global_skill_dir(home, agent) / "e8-skill-linker"
        create_symlink(entry, primary, True, args.link_type)
    print(json.dumps({"installed_self": plan}, ensure_ascii=False, indent=2))
    return 0


def init(args: argparse.Namespace) -> int:
    project = expand(args.project)
    execute = args.execute
    ensure_project_hub(project, execute)
    hub = project / ".agents" / "skills"
    for agent in parse_agents(args.agents):
        if agent == "claude":
            create_symlink(
                project / ".claude" / "skills",
                Path("..") / ".agents" / "skills",
                execute,
                args.link_type,
                allowed_roots=[hub],
            )
        elif agent == "codex":
            create_symlink(
                project / ".codex" / "skills",
                Path("..") / ".agents" / "skills",
                execute,
                args.link_type,
                allowed_roots=[hub],
            )
        elif agent == "agents":
            ensure_project_hub(project, execute)
        else:
            raise SystemExit(f"未知 Agent: {agent}")
    if not execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行")
    return 0


def link(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    source = expand(args.source)
    central = configured_central(project, home)
    project_hub = project / ".agents" / "skills"
    if not any(is_path_inside(source, root) for root in (central, project_hub)):
        raise SystemExit(
            "source 必须位于已配置中央 skills 库或当前项目 skills 库内；"
            f"source={source} central={central} project_hub={project_hub}"
        )
    if not source.exists() or not source.is_dir():
        raise SystemExit(f"源路径不存在或不是目录: {source}")
    if not (source / "SKILL.md").exists():
        raise SystemExit(f"源目录不包含 SKILL.md: {source}")
    name = args.name or source.name
    target = project / ".agents" / "skills" / name
    ensure_project_hub(project, args.execute)
    create_symlink(target, source, args.execute, args.link_type, allowed_roots=[central, project_hub])
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行")
    return 0


def link_many(args: argparse.Namespace) -> int:
    sources = [part.strip() for part in args.sources.split(",") if part.strip()]
    if not sources:
        raise SystemExit("没有提供可链接的 sources")
    exit_code = 0
    for raw_source in sources:
        child_args = argparse.Namespace(
            project=args.project,
            source=raw_source,
            name=None,
            execute=args.execute,
            link_type=args.link_type,
            home=args.home,
        )
        try:
            link(child_args)
        except SystemExit as exc:
            print(f"链接失败: {raw_source}: {exc}")
            exit_code = 1
    return exit_code


def check(args: argparse.Namespace) -> int:
    project = expand(args.project)
    problems = []
    for rel in PROJECT_SKILL_DIRS:
        directory = project / rel
        if not directory.exists() or not directory.is_dir():
            continue
        for entry in scan_skill_entries(directory):
            if entry.get("broken"):
                problems.append(entry)
            elif entry.get("is_dir") and not entry.get("has_skill_md"):
                problems.append(entry)
    print(json.dumps({"project": str(project), "problems": problems}, ensure_ascii=False, indent=2))
    return 1 if problems else 0


def remove_link_path(target: Path) -> None:
    if target.is_symlink():
        target.unlink()
        return
    if target.is_dir():
        target.rmdir()
        return
    target.unlink()


def unlink(args: argparse.Namespace) -> int:
    target = expand_preserve_link(args.target)
    item = classify(target)
    plan = {
        "target": item,
        "will_remove_link": item["is_symlink"] or item["is_junction"],
        "will_delete_real_directory": False,
        "note": "默认只删除软链接或 junction 本身，不删除中央 skill 原件。",
    }
    print(json.dumps({"planned_unlink": plan}, ensure_ascii=False, indent=2))
    if not target.exists() and not target.is_symlink():
        raise SystemExit(f"目标不存在: {target}")
    if not item["is_symlink"] and not item["is_junction"]:
        raise SystemExit("目标不是软链接或 junction。为了避免删除真实 skill 目录，已停止。")
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 删除链接本身")
        return 0
    remove_link_path(target)
    print(json.dumps({"unlinked": str(target), "deleted_original": False}, ensure_ascii=False, indent=2))
    return 0


def migrate(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    source = expand(args.source)
    central = expand(args.central)
    expected_central = configured_central(project, home)
    if central != expected_central:
        raise SystemExit(f"central 必须等于当前生效配置中的中央库: {expected_central}")
    if source.is_symlink():
        raise SystemExit(f"源路径已经是软链接，不需要迁移: {source}")
    if not source.exists() or not source.is_dir():
        raise SystemExit(f"源路径不存在或不是目录: {source}")
    if not (source / "SKILL.md").exists():
        raise SystemExit(f"源目录不包含 SKILL.md: {source}")
    name = args.name or source.name
    target = central / name
    if target.exists() or target.is_symlink():
        raise SystemExit(f"中央目录中已存在目标路径，默认不覆盖: {target}")
    plan = {
        "move": {"from": str(source), "to": str(target)},
        "create_symlink": {"path": str(source), "target": str(target)},
        "link_type": args.link_type,
        "will_delete_real_directory": False,
        "note": "执行时会把真实目录移动到中央目录，然后在原位置创建指向中央目录的软链接。",
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行迁移")
        return 0
    central.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    create_symlink(source, target, True, args.link_type, allowed_roots=[expected_central])
    print(json.dumps({"migrated": plan}, ensure_ascii=False, indent=2))
    return 0


def run_git(repo: Path, command: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *command],
        cwd=repo,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_output(repo: Path, command: list[str]) -> str | None:
    result = run_git(repo, command)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_root(path: Path) -> Path | None:
    if not path.exists():
        return None
    probe = path if path.is_dir() else path.parent
    result = run_git(probe, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve(strict=False)


def git_status_dict(repo: Path) -> dict:
    root = git_root(repo)
    if root is None:
        return {"path": str(repo), "is_git_repo": False}
    branch = git_output(root, ["branch", "--show-current"])
    upstream = git_output(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    status = git_output(root, ["status", "--short"]) or ""
    behind = None
    ahead = None
    if upstream:
        behind_raw = git_output(root, ["rev-list", "--count", f"HEAD..{upstream}"])
        ahead_raw = git_output(root, ["rev-list", "--count", f"{upstream}..HEAD"])
        behind = int(behind_raw) if behind_raw and behind_raw.isdigit() else None
        ahead = int(ahead_raw) if ahead_raw and ahead_raw.isdigit() else None
    return {
        "path": str(root),
        "is_git_repo": True,
        "branch": branch,
        "upstream": upstream,
        "dirty": bool(status),
        "status": status.splitlines(),
        "behind": behind,
        "ahead": ahead,
    }


def find_git_repos(path: Path) -> list[Path]:
    root = git_root(path)
    if root is not None:
        return [root]
    repos: list[Path] = []
    if not path.exists() or not path.is_dir():
        return repos
    for child in sorted(path.iterdir(), key=lambda p: p.name):
        if child.name.startswith(".") or not child.is_dir():
            continue
        child_root = git_root(child)
        if child_root is not None:
            repos.append(child_root)
    seen: set[str] = set()
    unique: list[Path] = []
    for repo in repos:
        key = str(repo)
        if key not in seen:
            seen.add(key)
            unique.append(repo)
    return unique


def git_status(args: argparse.Namespace) -> int:
    repo = expand(args.repo)
    print(json.dumps(git_status_dict(repo), ensure_ascii=False, indent=2))
    return 0


def updates(args: argparse.Namespace) -> int:
    central = expand(args.central)
    repos = find_git_repos(central)
    if args.execute:
        for repo in repos:
            print(f"获取远端更新信息: {repo}")
            result = run_git(repo, ["fetch", "--prune"])
            if result.returncode != 0:
                print(json.dumps({"path": str(repo), "fetch_error": result.stderr.strip()}, ensure_ascii=False))
    else:
        print("当前只是本地检查；远端是否有新提交可能不是最新。用户确认后传入 --execute 才会运行 git fetch --prune")
    report = [git_status_dict(repo) for repo in repos]
    print(json.dumps({"central": str(central), "repositories": report}, ensure_ascii=False, indent=2))
    return 0


def update_repo(args: argparse.Namespace) -> int:
    repo = expand(args.repo)
    status = git_status_dict(repo)
    if not status.get("is_git_repo"):
        raise SystemExit(f"不是 git 仓库: {repo}")
    print(json.dumps({"planned_update": status}, ensure_ascii=False, indent=2))
    if status.get("dirty") and not args.allow_dirty:
        raise SystemExit("仓库有本地改动；默认不更新。确认要继续时传入 --allow-dirty")
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行 git fetch --prune 和 git pull --ff-only")
        return 0
    root = Path(status["path"])
    fetch = run_git(root, ["fetch", "--prune"])
    if fetch.returncode != 0:
        raise SystemExit(fetch.stderr.strip())
    pull = run_git(root, ["pull", "--ff-only"])
    if pull.returncode != 0:
        raise SystemExit(pull.stderr.strip())
    print(pull.stdout.strip())
    print(json.dumps({"updated": git_status_dict(root)}, ensure_ascii=False, indent=2))
    return 0


def checkout(args: argparse.Namespace) -> int:
    repo = expand(args.repo)
    status = git_status_dict(repo)
    if not status.get("is_git_repo"):
        raise SystemExit(f"不是 git 仓库: {repo}")
    plan = {"repo": status, "checkout_ref": args.ref}
    print(json.dumps({"planned_checkout": plan}, ensure_ascii=False, indent=2))
    if status.get("dirty") and not args.allow_dirty:
        raise SystemExit("仓库有本地改动；默认不切换版本。确认要继续时传入 --allow-dirty")
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行 git checkout")
        return 0
    root = Path(status["path"])
    result = run_git(root, ["checkout", args.ref])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip())
    print(result.stdout.strip())
    print(json.dumps({"checked_out": git_status_dict(root)}, ensure_ascii=False, indent=2))
    return 0


def clone(args: argparse.Namespace) -> int:
    dest_parent = expand(args.dest_parent)
    repo_name = args.name or Path(args.repo_url.rstrip("/").removesuffix(".git")).name
    dest = dest_parent / repo_name
    plan = {
        "repo_url": args.repo_url,
        "destination": str(dest),
        "after_clone_detection": [
            "检查仓库根目录是否包含 SKILL.md",
            "检查 skills/*/SKILL.md",
            "检查 .agents/skills/*/SKILL.md",
        ],
    }
    print(json.dumps({"planned_clone": plan}, ensure_ascii=False, indent=2))
    if dest.exists():
        raise SystemExit(f"目标路径已存在，默认不覆盖: {dest}")
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行 git clone")
        return 0
    dest_parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", args.repo_url, str(dest)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip())
    print(result.stdout.strip())
    print(json.dumps({"cloned": str(dest), "skill_dirs": skill_dirs_in_repo(dest)}, ensure_ascii=False, indent=2))
    return 0


def parse_agents(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="安全管理 Agent skill 软链接。")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--project", default=".")
    inspect_parser.add_argument("--home", default="~")
    inspect_parser.set_defaults(func=inspect)

    config_parser = sub.add_parser("config")
    config_parser.add_argument("--project", default=".")
    config_parser.add_argument("--home", default="~")
    config_parser.add_argument("--scope", choices=["project", "user"], default="user")
    config_parser.add_argument("--central")
    config_parser.add_argument("--central-base")
    config_parser.add_argument("--mode", choices=sorted(VALID_DEFAULT_MODES), default="centralize")
    config_parser.add_argument("--execute", action="store_true")
    config_parser.set_defaults(func=config)

    install_self_parser = sub.add_parser("install-self")
    install_self_parser.add_argument("--source")
    install_self_parser.add_argument("--home", default="~")
    install_self_parser.add_argument("--agents", default="agents")
    install_self_parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    install_self_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    install_self_parser.add_argument("--replace", action="store_true")
    install_self_parser.add_argument("--execute", action="store_true")
    install_self_parser.set_defaults(func=install_self)

    init_parser = sub.add_parser("init")
    init_parser.add_argument("--project", default=".")
    init_parser.add_argument("--agents", default="claude,codex")
    init_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    init_parser.add_argument("--execute", action="store_true")
    init_parser.set_defaults(func=init)

    link_parser = sub.add_parser("link")
    link_parser.add_argument("--project", default=".")
    link_parser.add_argument("--home", default="~")
    link_parser.add_argument("--source", required=True)
    link_parser.add_argument("--name")
    link_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    link_parser.add_argument("--execute", action="store_true")
    link_parser.set_defaults(func=link)

    link_many_parser = sub.add_parser("link-many")
    link_many_parser.add_argument("--project", default=".")
    link_many_parser.add_argument("--home", default="~")
    link_many_parser.add_argument("--sources", required=True)
    link_many_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    link_many_parser.add_argument("--execute", action="store_true")
    link_many_parser.set_defaults(func=link_many)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--project", default=".")
    check_parser.set_defaults(func=check)

    unlink_parser = sub.add_parser("unlink")
    unlink_parser.add_argument("--target", required=True)
    unlink_parser.add_argument("--execute", action="store_true")
    unlink_parser.set_defaults(func=unlink)

    git_status_parser = sub.add_parser("git-status")
    git_status_parser.add_argument("--repo", required=True)
    git_status_parser.set_defaults(func=git_status)

    updates_parser = sub.add_parser("updates")
    updates_parser.add_argument("--central", required=True)
    updates_parser.add_argument("--execute", action="store_true")
    updates_parser.set_defaults(func=updates)

    update_parser = sub.add_parser("update")
    update_parser.add_argument("--repo", required=True)
    update_parser.add_argument("--allow-dirty", action="store_true")
    update_parser.add_argument("--execute", action="store_true")
    update_parser.set_defaults(func=update_repo)

    checkout_parser = sub.add_parser("checkout")
    checkout_parser.add_argument("--repo", required=True)
    checkout_parser.add_argument("--ref", required=True)
    checkout_parser.add_argument("--allow-dirty", action="store_true")
    checkout_parser.add_argument("--execute", action="store_true")
    checkout_parser.set_defaults(func=checkout)

    clone_parser = sub.add_parser("clone")
    clone_parser.add_argument("--repo-url", required=True)
    clone_parser.add_argument("--dest-parent", required=True)
    clone_parser.add_argument("--name")
    clone_parser.add_argument("--execute", action="store_true")
    clone_parser.set_defaults(func=clone)

    migrate_parser = sub.add_parser("migrate")
    migrate_parser.add_argument("--project", default=".")
    migrate_parser.add_argument("--home", default="~")
    migrate_parser.add_argument("--source", required=True)
    migrate_parser.add_argument("--central", required=True)
    migrate_parser.add_argument("--name")
    migrate_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    migrate_parser.add_argument("--execute", action="store_true")
    migrate_parser.set_defaults(func=migrate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
