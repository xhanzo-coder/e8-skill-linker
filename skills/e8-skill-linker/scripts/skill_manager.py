#!/usr/bin/env python3
"""检查并管理 Agent skills 的中央库与项目级入口。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


PROJECT_SKILL_DIRS = (".agents/skills", ".codex/skills", ".claude/skills")
USER_SKILL_DIRS = ("~/.agents/skills", "~/.codex/skills", "~/.claude/skills")
DEFAULT_CENTRAL_DIR = "~/.e8-skill-linker/AgentSkills"
EXTRA_NON_GLOBAL_CENTRAL_DIRS = ["~/Skills"]
CENTRAL_NAMESPACE = Path(".e8-skill-linker") / "AgentSkills"
CONFIG_FILENAME = ".skill-linker.json"
CONFIG_SCHEMA_VERSION = 2
DEFAULT_LIBRARY_NAME = "personal"
REPOSITORY_DIRNAME = ".repos"
REGISTRY_FILENAME = ".skill-linker-lock.json"
REGISTRY_SCHEMA_VERSION = 1
VALID_DEFAULT_MODES = {"ask", "centralize", "project-local"}
IS_WINDOWS = platform.system() == "Windows"
VERSION = "0.2.0"


def expand(path: str | Path) -> Path:
    return Path(path).expanduser().absolute()


def expand_with_home(path: str | Path, home: Path) -> Path:
    raw = str(path)
    if raw == "~" or raw.startswith("~/"):
        raw = raw.replace("~", str(home), 1)
    return Path(raw).expanduser()


def expand_preserve_link(path: str | Path) -> Path:
    return Path(path).expanduser().absolute()


def path_lexists(path: Path) -> bool:
    return path.exists() or path.is_symlink() or is_junction(path)


def canonical(path: str | Path) -> Path:
    return expand(path).resolve(strict=False)


def resolve_from(raw: str | Path, home: Path, base: Path) -> Path:
    path = expand_with_home(raw, home)
    if not path.is_absolute():
        path = base / path
    return path.absolute()


def classify(path: Path, include_entries: bool = False) -> dict:
    symlink = path.is_symlink()
    junction = is_junction(path)
    item = {
        "path": str(path),
        "exists": path.exists(),
        "is_symlink": symlink,
        "is_junction": junction,
        "is_dir": path.is_dir(),
        "target": None,
        "broken": False,
        "has_skill_md": False,
        "entries": [],
    }
    if symlink or junction:
        target = Path(os.path.realpath(path))
        item["target"] = str(target)
        item["immediate_target"] = str(immediate_link_target(path))
        item["broken"] = not target.exists()
    if path.exists() and path.is_dir():
        item["has_skill_md"] = (path / "SKILL.md").exists()
        if include_entries:
            item["entries"] = scan_skill_entries(path)
    return item


def is_junction(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    if checker is not None:
        return bool(checker())
    if not IS_WINDOWS or path.is_symlink() or not os.path.lexists(path):
        return False
    attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


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
    return expand_with_home(DEFAULT_CENTRAL_DIR, home).absolute()


def central_from_base(base: Path) -> Path:
    return base / CENTRAL_NAMESPACE


def has_central_namespace(path: Path) -> bool:
    parts = path.parts
    return len(parts) >= 2 and parts[-2:] == CENTRAL_NAMESPACE.parts


def user_skill_paths(home: Path) -> list[Path]:
    return [expand_with_home(raw, home).absolute() for raw in USER_SKILL_DIRS]


def is_global_agent_dir(path: Path, home: Path) -> bool:
    probe = canonical(path)
    return any(probe == canonical(candidate) for candidate in user_skill_paths(home))


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


def validate_library_name(name: str) -> str:
    if not isinstance(name, str) or len(name) > 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("中央库名称必须为 1-64 位小写字母、数字或单个连字符分隔的片段")
    return name


def command_library_name(name: str) -> str:
    try:
        return validate_library_name(name)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def config_data(libraries: dict[str, Path], active_library: str, default_mode: str) -> dict:
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "libraries": {name: {"path": str(path)} for name, path in sorted(libraries.items())},
        "active_library": active_library,
        "default_mode": default_mode,
    }


def normalize_config(path: Path, scope: str, data: dict, home: Path) -> dict:
    if "schema_version" not in data:
        if set(data) == {"central_skills_dir", "default_mode"}:
            raise ValueError("检测到 v1 配置；请先运行 migrate-config 显式升级到 schema_version 2")
        raise ValueError("配置缺少必需字段: ['schema_version']")
    required = {"schema_version", "libraries", "active_library", "default_mode"}
    missing = required.difference(data)
    if missing:
        raise ValueError(f"配置缺少必需字段: {sorted(missing)}")
    unknown = set(data).difference(required)
    if unknown:
        raise ValueError(f"配置包含未知字段: {sorted(unknown)}")
    if data["schema_version"] != CONFIG_SCHEMA_VERSION:
        raise ValueError(f"schema_version 必须为 {CONFIG_SCHEMA_VERSION}")
    raw_libraries = data["libraries"]
    if not isinstance(raw_libraries, dict) or not raw_libraries:
        raise ValueError("libraries 必须是非空 JSON object")
    libraries: dict[str, dict] = {}
    canonical_paths: dict[Path, str] = {}
    for name, raw_library in raw_libraries.items():
        validate_library_name(name)
        if not isinstance(raw_library, dict) or set(raw_library) != {"path"}:
            raise ValueError(f"中央库 {name} 必须仅包含非空 path 字段")
        raw_path = raw_library["path"]
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"中央库 {name} 的 path 必须是非空字符串")
        central = resolve_from(raw_path, home, path.parent)
        canonical_path = canonical(central)
        if canonical_path in canonical_paths:
            raise ValueError(f"中央库 {name} 与 {canonical_paths[canonical_path]} 指向同一路径")
        canonical_paths[canonical_path] = name
        warning = global_dir_warning(central, home)
        libraries[name] = {
            "path": str(central),
            "exists": central.exists() and central.is_dir(),
            "is_global_agent_dir": bool(warning),
            "warning": warning,
        }
    active_library = data["active_library"]
    if not isinstance(active_library, str):
        raise ValueError("active_library 必须是字符串")
    validate_library_name(active_library)
    if active_library not in libraries:
        raise ValueError(f"active_library 不存在于 libraries: {active_library}")
    mode = data["default_mode"]
    if not isinstance(mode, str) or mode not in VALID_DEFAULT_MODES:
        raise ValueError(f"default_mode 必须是 {sorted(VALID_DEFAULT_MODES)} 之一")
    active = libraries[active_library]
    return {
        "source": scope,
        "path": str(path),
        "schema_version": CONFIG_SCHEMA_VERSION,
        "libraries": libraries,
        "active_library": active_library,
        "central_skills_dir": active["path"],
        "central_exists": active["exists"],
        "central_is_global_agent_dir": active["is_global_agent_dir"],
        "warning": active["warning"],
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
        "schema_version": None,
        "libraries": {},
        "active_library": None,
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
        configured_path = expand(configured)
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
        candidate = expand_with_home(raw, home).absolute()
        if candidate.exists():
            candidates.append(candidate)
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        key = str(canonical(candidate))
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def collect_duplicate_names(groups: Iterable[dict]) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for group in groups:
        for entry in group["entries"]:
            name = entry["name"]
            if name and not name.startswith("<"):
                seen.setdefault(name, []).append(entry["path"])
    return {name: paths for name, paths in seen.items() if len(paths) > 1}


def inspect(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    config = load_effective_config(project, home)
    project_dirs = [classify(project / rel, include_entries=True) for rel in PROJECT_SKILL_DIRS]
    user_dirs = [classify(expand_with_home(rel, home).absolute(), include_entries=True) for rel in USER_SKILL_DIRS]
    configured = None if config["source"] == "error" else config["central_skills_dir"]
    central_inventory = None
    if configured is not None:
        central = Path(configured)
        central_inventory = {
            "library": config["active_library"],
            "root": classify(central, include_entries=True),
            "repository_store": classify(repository_store(central), include_entries=False),
            "registry": registry_summary(central),
        }
    report = {
        "project": str(project),
        "config": config,
        "project_skill_dirs": project_dirs,
        "user_skill_dirs": user_dirs,
        "global_agent_dirs": global_agent_dirs(home),
        "recommended_default_central_dir": str(default_central_dir(home).resolve(strict=False)),
        "central_candidates": candidate_central_dirs(home, configured),
        "central_inventory": central_inventory,
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

    central_base = resolve_from(args.central_base, home, project) if args.central_base else None
    central = central_from_base(central_base) if central_base else resolve_from(args.central, home, project)
    target = project / CONFIG_FILENAME if args.scope == "project" else home / CONFIG_FILENAME
    library_name = command_library_name(args.library)
    data = config_data({library_name: central}, library_name, args.mode)
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
        "will_replace_config": target.exists(),
        "central_is_global_agent_dir": bool(warning),
        "warnings": warnings,
        "recommended_default_central_dir": str(default_central_dir(home).resolve(strict=False)),
    }
    print(json.dumps({"planned_config": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 写入配置文件")
        return 0
    if warning and not args.allow_global_central:
        raise SystemExit("中央目录是 Agent 全局 skills 目录；明确确认后增加 --allow-global-central")
    if namespace_warning(central) and not args.allow_non_namespaced_central:
        raise SystemExit(
            "中央目录缺少 .e8-skill-linker/AgentSkills 命名空间；"
            "明确确认这是最终目录后增加 --allow-non-namespaced-central"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    central.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written_config": str(target)}, ensure_ascii=False, indent=2))
    return 0


def config_path_for_scope(project: Path, home: Path, scope: str) -> Path:
    if scope == "project":
        return project / CONFIG_FILENAME
    if scope == "user":
        return home / CONFIG_FILENAME
    raise SystemExit(f"未知配置作用域: {scope}")


def load_scoped_config(project: Path, home: Path, scope: str) -> tuple[Path, dict, dict]:
    path = config_path_for_scope(project, home, scope)
    data = read_config_file(path)
    if data is None:
        raise SystemExit(f"配置文件不存在: {path}")
    try:
        normalized = normalize_config(path, scope, data, home)
    except ValueError as exc:
        raise SystemExit(f"配置错误: {exc}") from exc
    return path, data, normalized


def migration_data(path: Path, data: dict, home: Path, library_name: str) -> dict:
    if set(data) != {"central_skills_dir", "default_mode"}:
        raise SystemExit("只能迁移字段为 central_skills_dir + default_mode 的 v1 配置")
    central_raw = data["central_skills_dir"]
    mode = data["default_mode"]
    if not isinstance(central_raw, str) or not central_raw.strip():
        raise SystemExit("v1 central_skills_dir 必须是非空字符串")
    if not isinstance(mode, str) or mode not in VALID_DEFAULT_MODES:
        raise SystemExit(f"v1 default_mode 必须是 {sorted(VALID_DEFAULT_MODES)} 之一")
    central = resolve_from(central_raw, home, path.parent)
    validated_name = command_library_name(library_name)
    return config_data({validated_name: central}, validated_name, mode)


def migrate_config(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    target = config_path_for_scope(project, home, args.scope)
    data = read_config_file(target)
    if data is None:
        raise SystemExit(f"配置文件不存在: {target}")
    migrated = migration_data(target, data, home, args.library)
    central = Path(migrated["libraries"][args.library]["path"])
    warning = global_dir_warning(central, home)
    warnings = [item for item in (warning, namespace_warning(central)) if item]
    plan = {
        "config_path": str(target),
        "from_schema": 1,
        "to_schema": CONFIG_SCHEMA_VERSION,
        "config": migrated,
        "warnings": warnings,
        "will_create_central_dir": not central.exists(),
    }
    print(json.dumps({"planned_config_migration": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 升级配置")
        return 0
    if warning and not args.allow_global_central:
        raise SystemExit("中央目录是 Agent 全局 skills 目录；明确确认后增加 --allow-global-central")
    if namespace_warning(central) and not args.allow_non_namespaced_central:
        raise SystemExit("中央目录缺少 .e8-skill-linker/AgentSkills 命名空间；明确确认后增加 --allow-non-namespaced-central")
    central.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"migrated_config": str(target)}, ensure_ascii=False, indent=2))
    return 0


def library_list(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    report: dict[str, object] = {"effective": load_effective_config(project, home), "scopes": {}}
    scopes = report["scopes"]
    assert isinstance(scopes, dict)
    for scope in ("project", "user"):
        path = config_path_for_scope(project, home, scope)
        data = read_config_file(path)
        if data is None:
            scopes[scope] = {"path": str(path), "exists": False}
            continue
        try:
            scopes[scope] = normalize_config(path, scope, data, home)
        except ValueError as exc:
            scopes[scope] = {"path": str(path), "exists": True, "error": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def library_add(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    path, _, normalized = load_scoped_config(project, home, args.scope)
    name = command_library_name(args.name)
    if name in normalized["libraries"]:
        raise SystemExit(f"中央库名称已存在: {name}")
    if args.central and args.central_base:
        raise SystemExit("不能同时提供 --central 和 --central-base")
    if not args.central and not args.central_base:
        raise SystemExit("必须提供 --central 或 --central-base")
    base = resolve_from(args.central_base, home, project) if args.central_base else None
    central = central_from_base(base) if base else resolve_from(args.central, home, project)
    libraries = {library_name: Path(item["path"]) for library_name, item in normalized["libraries"].items()}
    if any(canonical(existing) == canonical(central) for existing in libraries.values()):
        raise SystemExit(f"该中央库路径已登记: {central}")
    libraries[name] = central
    active = name if args.activate else normalized["active_library"]
    data = config_data(libraries, active, normalized["default_mode"])
    warning = global_dir_warning(central, home)
    plan = {
        "config_path": str(path),
        "add_library": {"name": name, "path": str(central)},
        "activate": args.activate,
        "will_create_central_dir": not central.exists(),
        "warnings": [item for item in (warning, None if base else namespace_warning(central)) if item],
    }
    print(json.dumps({"planned_library_add": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 添加中央库")
        return 0
    if warning and not args.allow_global_central:
        raise SystemExit("中央目录是 Agent 全局 skills 目录；明确确认后增加 --allow-global-central")
    if namespace_warning(central) and not args.allow_non_namespaced_central:
        raise SystemExit("中央目录缺少 .e8-skill-linker/AgentSkills 命名空间；明确确认后增加 --allow-non-namespaced-central")
    central.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added_library": plan}, ensure_ascii=False, indent=2))
    return 0


def library_use(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    path, _, normalized = load_scoped_config(project, home, args.scope)
    name = command_library_name(args.name)
    if name not in normalized["libraries"]:
        raise SystemExit(f"中央库不存在: {name}")
    libraries = {library_name: Path(item["path"]) for library_name, item in normalized["libraries"].items()}
    data = config_data(libraries, name, normalized["default_mode"])
    plan = {
        "config_path": str(path),
        "from": normalized["active_library"],
        "to": name,
        "central_skills_dir": str(libraries[name]),
        "existing_project_links": project_link_inventory(project, libraries),
        "note": "只切换该配置作用域的活动中央库；不会静默重写现有项目链接。",
    }
    print(json.dumps({"planned_library_use": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 切换活动中央库")
        return 0
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"active_library": name, "config_path": str(path)}, ensure_ascii=False, indent=2))
    return 0


def ensure_project_hub(project: Path, execute: bool) -> None:
    hub = project / ".agents" / "skills"
    if path_lexists(hub):
        if not hub.is_dir():
            raise SystemExit(f"项目 skill hub 已存在但不是可用目录: {hub}")
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


def selected_libraries(project: Path, home: Path, library: str | None, all_libraries: bool) -> dict[str, Path]:
    """Select only from the effective config; never mutate its default selection."""
    config = load_effective_config(project, home)
    if config["source"] == "error":
        raise SystemExit(f"中央库配置错误: {config['error']}")
    if config["source"] is None:
        raise SystemExit("未配置中央库；请先创建 .skill-linker.json")
    if library is not None and all_libraries:
        raise SystemExit("--library 与 --all-libraries 不能同时使用")
    names = list(config["libraries"]) if all_libraries else [library if library is not None else config["active_library"]]
    result = {}
    for name in names:
        if name not in config["libraries"]:
            raise SystemExit(f"当前生效配置中不存在中央库: {name}")
        central = Path(config["libraries"][name]["path"])
        if not central.is_dir():
            raise SystemExit(f"已配置中央库不存在或不是目录: {central}")
        result[name] = central
    return result


def configured_central(project: Path, home: Path, library: str | None = None) -> Path:
    return next(iter(selected_libraries(project, home, library, False).values()))


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


def validate_skill_name(name: str) -> str:
    if not name or name in {".", ".."}:
        raise SystemExit("skill 名称不能为空或为 . / ..")
    if Path(name).name != name or Path(name).is_absolute():
        raise SystemExit(f"skill 名称必须是单个目录名，拒绝路径穿越: {name}")
    if name.startswith("."):
        raise SystemExit(f"skill 名称不能以 . 开头: {name}")
    return name


def validate_directory_name(name: str, label: str) -> str:
    if not name or name in {".", ".."}:
        raise SystemExit(f"{label} 不能为空或为 . / ..")
    if Path(name).name != name or Path(name).is_absolute():
        raise SystemExit(f"{label} 必须是单个目录名，拒绝路径穿越: {name}")
    return name


def validate_git_argument(value: str, label: str) -> str:
    if not value or value.startswith("-"):
        raise SystemExit(f"{label} 不能为空或以 - 开头: {value}")
    return value


def create_windows_junction(link: Path, target: Path) -> None:
    # Keep the central entry in the reparse point instead of dereferencing it.
    target_abs = target if target.is_absolute() else link.parent / target
    target_abs = Path(os.path.abspath(target_abs))
    result = subprocess.run(
        ["cmd", "/u", "/c", "mklink", "/J", str(link), str(target_abs)],
        text=True,
        encoding="utf-16-le",
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
    destination_state = validate_link_destination(link, target)
    if destination_state == "same-link":
        print(f"无需修改，已指向目标: {link} -> {canonical(resolve_link_target(link, target))}")
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


def immediate_link_target(link: Path) -> Path:
    """Read one link hop, including Windows junctions, without resolving its target."""
    raw = os.readlink(link)
    if raw.startswith("\\\\?\\UNC\\"):
        raw = "\\\\" + raw[8:]
    elif raw.startswith("\\\\?\\"):
        raw = raw[4:]
    target = Path(raw)
    return Path(os.path.abspath(target if target.is_absolute() else link.parent / target))


def validate_link_destination(link: Path, target: Path) -> str:
    if link.exists() or link.is_symlink() or is_junction(link):
        current = classify(link)
        expected = Path(os.path.abspath(target if target.is_absolute() else link.parent / target))
        if (current["is_symlink"] or current["is_junction"]) and immediate_link_target(link) == expected and not current["broken"]:
            return "same-link"
        if current["is_symlink"] or current["is_junction"]:
            raise SystemExit(
                f"目标已有其他链接，默认不替换: {link} "
                f"current={current['target']} expected={expected}"
            )
        raise SystemExit(f"目标已有真实路径，默认不覆盖: {link}")
    return "absent"


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


def read_skill_name(skill_dir: Path) -> str:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise SystemExit(f"源目录不包含 SKILL.md: {skill_dir}")
    return parse_skill_name(skill_file.read_text(encoding="utf-8"), str(skill_file))


def parse_skill_name(text: str, source: str) -> str:
    """Parse the same identity from a worktree file or a candidate Git blob."""
    skill_file = source
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"SKILL.md 缺少 YAML frontmatter: {skill_file}")
    name = None
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        match = re.fullmatch(r"\s*name\s*:\s*([^#]+?)\s*", line)
        if match:
            if name is not None:
                raise SystemExit(f"SKILL.md frontmatter 包含重复 name: {skill_file}")
            name = match.group(1).strip().strip("\"'")
    if not closed:
        raise SystemExit(f"SKILL.md frontmatter 缺少结束分隔符: {skill_file}")
    if name is None:
        raise SystemExit(f"SKILL.md frontmatter 缺少 name: {skill_file}")
    return validate_skill_name(name)


def repository_store(central: Path) -> Path:
    return central / REPOSITORY_DIRNAME


def registry_path(central: Path) -> Path:
    return central / REGISTRY_FILENAME


def read_registry(central: Path) -> dict:
    path = registry_path(central)
    if not path.exists():
        store = repository_store(central)
        if store.exists() and any(store.iterdir()):
            raise SystemExit(f"仓库存储非空但缺少来源清单，无法确认来源: {path}")
        return {"schema_version": REGISTRY_SCHEMA_VERSION, "repositories": {}}
    try:
        data = read_config_file(path)
    except ValueError as exc:
        raise SystemExit(f"仓库清单无法读取: {exc}") from exc
    assert data is not None
    if set(data) != {"schema_version", "repositories"}:
        raise SystemExit(f"仓库清单字段不合法: {path}")
    if data["schema_version"] != REGISTRY_SCHEMA_VERSION:
        raise SystemExit(f"仓库清单 schema_version 必须为 {REGISTRY_SCHEMA_VERSION}: {path}")
    if not isinstance(data["repositories"], dict):
        raise SystemExit(f"仓库清单 repositories 必须是 JSON object: {path}")
    skill_owners: set[str] = set()
    repo_paths: set[Path] = set()
    for repo_id, record in data["repositories"].items():
        if not isinstance(repo_id, str) or not repo_id:
            raise SystemExit(f"仓库清单包含无效仓库 ID: {path}")
        if not isinstance(record, dict) or set(record) != {"url", "path", "revision", "skills"}:
            raise SystemExit(f"仓库清单记录字段不合法: {repo_id}")
        if not isinstance(record["url"], str) or not record["url"]:
            raise SystemExit(f"仓库清单 URL 无效: {repo_id}")
        if not isinstance(record["revision"], str) or not re.fullmatch(r"[0-9a-fA-F]{40,64}", record["revision"]):
            raise SystemExit(f"仓库清单 revision 无效: {repo_id}")
        if not isinstance(record["path"], str):
            raise SystemExit(f"仓库清单路径必须是字符串: {repo_id}")
        repo_path = Path(record["path"])
        if repo_path.is_absolute() or ".." in repo_path.parts:
            raise SystemExit(f"仓库清单路径必须是安全相对路径: {repo_id}")
        if len(repo_path.parts) < 4 or repo_path.parts[0] != REPOSITORY_DIRNAME:
            raise SystemExit(f"仓库必须位于 .repos/<host>/<namespace>/<repo>: {repo_id}")
        resolved = canonical(central / repo_path)
        if not is_path_inside(resolved, repository_store(central)) or resolved in repo_paths:
            raise SystemExit(f"仓库清单路径越界或重复: {repo_id}")
        repo_paths.add(resolved)
        if not isinstance(record["skills"], dict):
            raise SystemExit(f"仓库清单 skills 必须是 JSON object: {repo_id}")
        for skill_name, skill_record in record["skills"].items():
            validate_skill_name(skill_name)
            if skill_name in skill_owners:
                raise SystemExit(f"中央入口被多个仓库登记: {skill_name}")
            skill_owners.add(skill_name)
            if not isinstance(skill_record, dict) or set(skill_record) != {"subpath", "entry"}:
                raise SystemExit(f"仓库清单 skill 记录字段不合法: {repo_id}/{skill_name}")
            if skill_record["entry"] != skill_name:
                raise SystemExit(f"仓库清单 entry 必须匹配 skill 名称: {repo_id}/{skill_name}")
            if not isinstance(skill_record["subpath"], str):
                raise SystemExit(f"仓库清单 skill 子路径必须是字符串: {repo_id}/{skill_name}")
            subpath = Path(skill_record["subpath"])
            if subpath.is_absolute() or ".." in subpath.parts:
                raise SystemExit(f"仓库清单 skill 子路径无效: {repo_id}/{skill_name}")
    return data


def registry_summary(central: Path) -> dict:
    registry = read_registry(central)
    repositories = registry["repositories"]
    skill_count = sum(len(record["skills"]) for record in repositories.values())
    return {
        "path": str(registry_path(central)),
        "exists": registry_path(central).exists(),
        "repository_count": len(repositories),
        "skill_count": skill_count,
    }


def write_registry(central: Path, data: dict) -> None:
    central.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=central,
        prefix=f"{REGISTRY_FILENAME}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    try:
        os.replace(temporary, registry_path(central))
    finally:
        if temporary.exists():
            temporary.unlink()


def repository_identity(repo_url: str) -> tuple[str, list[str]]:
    local = Path(repo_url).expanduser()
    if local.exists():
        repo_name = validate_directory_name(local.name.removesuffix(".git"), "仓库目录名")
        owner = validate_directory_name(local.parent.name or "root", "本地仓库父目录名")
        return f"local/{owner}/{repo_name}", ["local", owner, repo_name]
    scp_match = re.fullmatch(r"[^@\s]+@([^:\s]+):(.+)", repo_url)
    if scp_match:
        host = scp_match.group(1).lower()
        raw_parts = scp_match.group(2).strip("/").removesuffix(".git").split("/")
    else:
        parsed = urlparse(repo_url)
        if not parsed.scheme or not parsed.hostname:
            raise SystemExit("仓库 URL 必须是可解析的 Git URL 或存在的本地路径")
        host = parsed.hostname.lower()
        raw_parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if len(raw_parts) < 2:
        raise SystemExit(f"仓库 URL 缺少 owner/repository: {repo_url}")
    namespace = [validate_directory_name(part, "仓库 namespace") for part in raw_parts]
    host_part = validate_directory_name(host, "仓库 host")
    parts = [host_part, *namespace]
    return "/".join(parts), parts


def parse_skill_specs(raw: str) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for token in [part.strip() for part in raw.split(",") if part.strip()]:
        if "=" not in token:
            raise SystemExit("--skills 必须使用 name=relative/path 格式，多项用逗号分隔")
        raw_name, raw_subpath = token.split("=", 1)
        name = validate_skill_name(raw_name.strip())
        subpath = Path(raw_subpath.strip())
        if not raw_subpath.strip() or subpath.is_absolute() or ".." in subpath.parts:
            raise SystemExit(f"skill 子路径必须是仓库内的安全相对路径: {raw_subpath}")
        if subpath != Path(".") and subpath.name != name:
            raise SystemExit(f"skill 名称必须匹配子路径目录名: name={name} path={subpath}")
        specs.append({"name": name, "subpath": subpath.as_posix()})
    if not specs:
        raise SystemExit("--skills 至少需要一个 name=relative/path")
    names = [item["name"] for item in specs]
    if len(names) != len(set(names)):
        raise SystemExit("--skills 包含重复的 skill 名称")
    return specs


def cleanup_empty_repo_parents(repo_dest: Path, store: Path) -> None:
    current = repo_dest.parent
    while current != store and store in current.parents:
        if any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent


def install_repo(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    central = configured_central(project, home, args.library)
    repo_url = validate_git_argument(args.repo_url, "repo URL")
    repo_id, storage_parts = repository_identity(repo_url)
    specs = parse_skill_specs(args.skills)
    store = repository_store(central)
    repo_dest = store.joinpath(*storage_parts)
    registry = read_registry(central)
    reuse = repo_id in registry["repositories"]
    if reuse:
        record = registry["repositories"][repo_id]
        if record["url"] != repo_url or canonical(central / record["path"]) != canonical(repo_dest):
            raise SystemExit(f"仓库来源与已登记记录不一致: {repo_id}")
        validate_registered_repository(central, record)
        for spec in specs:
            if spec["name"] in record["skills"] and record["skills"][spec["name"]]["subpath"] != spec["subpath"]:
                raise SystemExit(f"已登记 skill 的子路径不同: {spec['name']}")
    elif path_lexists(repo_dest):
        raise SystemExit(f"仓库目标已存在，默认不覆盖: {repo_dest}")
    for owner_id, record in registry["repositories"].items():
        if owner_id != repo_id and any(spec["name"] in record["skills"] for spec in specs):
            raise SystemExit(f"skill 名称已由其他仓库登记: {owner_id}")
    central_entries = [(central / item["name"], repo_dest / item["subpath"]) for item in specs]
    project_hub = project / ".agents" / "skills"
    project_entries = [(project_hub / item["name"], central / item["name"]) for item in specs] if args.enable_project else []
    central_states = [validate_link_destination(entry, target) for entry, target in central_entries]
    project_states = [validate_link_destination(entry, target) for entry, target in project_entries]
    plan = {
        "repository": {"id": repo_id, "url": repo_url, "destination": str(repo_dest)},
        "central_library": str(central),
        "reuse_repository": reuse,
        "central_entries": [{"path": str(entry), "target": str(target)} for entry, target in central_entries],
        "project_entries": [{"path": str(entry), "target": str(target)} for entry, target in project_entries],
        "registry": str(registry_path(central)),
        "will_delete_existing_content": False,
    }
    print(json.dumps({"planned_repo_install": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行原子安装")
        return 0
    if not reuse:
        repo_dest.parent.mkdir(parents=True, exist_ok=True)
        clone_result = subprocess.run(
            ["git", "clone", "--", repo_url, str(repo_dest)],
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if clone_result.returncode != 0:
            if repo_dest.exists():
                remove_directory_tree(repo_dest)
            cleanup_empty_repo_parents(repo_dest, store)
            raise SystemExit(clone_result.stderr.strip())
    created_central: list[Path] = []
    created_project: list[Path] = []
    project_hub_existed = project_hub.exists()
    try:
        for spec in specs:
            skill_dir = repo_dest / spec["subpath"]
            if not is_path_inside(skill_dir, repo_dest):
                raise SystemExit(f"skill 路径越出仓库: {skill_dir}")
            actual_name = read_skill_name(skill_dir)
            if spec["subpath"] != "." and skill_dir.name != actual_name:
                raise SystemExit(
                    f"skill 目录名与 SKILL.md name 不一致: directory={skill_dir.name} name={actual_name}"
                )
            if actual_name != spec["name"]:
                raise SystemExit(
                    f"skill name 与安装计划不一致: expected={spec['name']} actual={actual_name} path={skill_dir}"
                )
        for (entry, target), state in zip(central_entries, central_states):
            create_symlink(entry, target, True, args.link_type, allowed_roots=[central])
            if state == "absent":
                created_central.append(entry)
        if project_entries:
            ensure_project_hub(project, True)
            for (entry, target), state in zip(project_entries, project_states):
                create_symlink(entry, target, True, args.link_type, allowed_roots=[central, project_hub])
                if state == "absent":
                    created_project.append(entry)
        revision = git_output(repo_dest, ["rev-parse", "HEAD"])
        if revision is None:
            raise SystemExit(f"无法读取已克隆仓库的 HEAD: {repo_dest}")
        if not reuse:
            registry["repositories"][repo_id] = {
                "url": repo_url,
                "path": repo_dest.relative_to(central).as_posix(),
                "revision": revision,
                "skills": {},
            }
        registry["repositories"][repo_id]["skills"].update({
            spec["name"]: {"subpath": spec["subpath"], "entry": spec["name"]} for spec in specs
        })
        validate_registered_repository(central, registry["repositories"][repo_id])
        write_registry(central, registry)
    except (OSError, SystemExit):
        for entry in reversed(created_project):
            remove_link_path(entry)
        for entry in reversed(created_central):
            remove_link_path(entry)
        if not project_hub_existed and project_hub.exists() and not any(project_hub.iterdir()):
            project_hub.rmdir()
        if not reuse:
            remove_directory_tree(repo_dest)
            cleanup_empty_repo_parents(repo_dest, store)
        raise
    print(json.dumps({"installed_repository": plan}, ensure_ascii=False, indent=2))
    return 0


def user_global_skill_dir(home: Path, agent: str) -> Path:
    if agent == "agents":
        return home / ".agents" / "skills"
    if agent == "codex":
        return home / ".codex" / "skills"
    if agent == "claude":
        return home / ".claude" / "skills"
    raise SystemExit(f"未知 Agent: {agent}")


def backup_path(home: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = home / ".e8-skill-linker" / "backups" / "e8-skill-linker"
    candidate = root / stamp
    counter = 1
    while path_lexists(candidate):
        candidate = root / f"{stamp}-{counter}"
        counter += 1
    return candidate


def remove_tree_error(function, path: str, exc_info) -> None:
    del exc_info
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_directory_tree(path: Path) -> None:
    shutil.rmtree(path, onerror=remove_tree_error)


def install_self(args: argparse.Namespace) -> int:
    home = expand(args.home)
    source = expand(args.source) if args.source else Path(__file__).resolve(strict=False).parents[1]
    if not source.exists() or not source.is_dir() or not (source / "SKILL.md").exists():
        raise SystemExit(f"source 必须是包含 SKILL.md 的 e8-skill-linker 目录: {source}")
    agents = parse_agents(args.agents)
    primary = user_global_skill_dir(home, "agents") / "e8-skill-linker"
    source_canonical = canonical(source)
    primary_canonical = canonical(primary)
    if source_canonical == primary_canonical:
        print(json.dumps({"already_installed": str(primary)}, ensure_ascii=False, indent=2))
        entries = []
        for agent in agents:
            if agent == "agents":
                continue
            entry = user_global_skill_dir(home, agent) / "e8-skill-linker"
            validate_link_destination(entry, primary)
            entries.append(entry)
        for entry in entries:
            create_symlink(entry, primary, args.execute, args.link_type)
        return 0
    if source_canonical in primary_canonical.parents:
        raise SystemExit(f"source 不能包含目标全局 skill 目录，否则会递归复制: {source}")
    plan = {
        "source": str(source),
        "install_primary": str(primary),
        "mode": args.mode,
        "agent_entries": [],
        "will_overwrite": False,
        "note": "e8-skill-linker 是管理型 skill，可作为例外安装到用户级全局目录；业务型 skills 不应因此默认全局安装。",
    }
    if path_lexists(primary):
        plan["existing_primary"] = classify(primary)
        if not args.replace:
            print(json.dumps({"planned_install_self": plan}, ensure_ascii=False, indent=2))
            raise SystemExit("全局 e8-skill-linker 已存在；默认不覆盖。确认替换时传入 --replace")
        plan["will_overwrite"] = True
        plan["backup_existing_to"] = str(backup_path(home))
    secondary_entries = []
    for agent in agents:
        entry = user_global_skill_dir(home, agent) / "e8-skill-linker"
        target = primary if agent != "agents" else source
        plan["agent_entries"].append({"agent": agent, "path": str(entry), "target": str(target)})
        if agent != "agents":
            state = validate_link_destination(entry, primary)
            secondary_entries.append((entry, state))
    print(json.dumps({"planned_install_self": plan}, ensure_ascii=False, indent=2))
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 安装 e8-skill-linker")
        return 0
    existing_backup = None
    if path_lexists(primary):
        existing_backup = Path(plan["backup_existing_to"])
        existing_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(primary), str(existing_backup))
    primary.parent.mkdir(parents=True, exist_ok=True)
    created_entries = []
    try:
        if args.mode == "copy":
            shutil.copytree(
                source,
                primary,
                symlinks=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        else:
            create_symlink(primary, source, True, args.link_type)
        for entry, state in secondary_entries:
            create_symlink(entry, primary, True, args.link_type)
            if state == "absent":
                created_entries.append(entry)
    except (OSError, SystemExit):
        for entry in reversed(created_entries):
            remove_link_path(entry)
        if primary.is_symlink():
            primary.unlink()
        elif is_junction(primary):
            primary.rmdir()
        elif primary.is_dir():
            remove_directory_tree(primary)
        elif os.path.lexists(primary):
            primary.unlink()
        if existing_backup is not None:
            shutil.move(str(existing_backup), str(primary))
        raise
    print(json.dumps({"installed_self": plan}, ensure_ascii=False, indent=2))
    return 0


def init(args: argparse.Namespace) -> int:
    project = expand(args.project)
    execute = args.execute
    hub = project / ".agents" / "skills"
    agents = parse_agents(args.agents)
    entries = []
    for agent in agents:
        if agent == "claude":
            entries.append((project / ".claude" / "skills", Path("..") / ".agents" / "skills"))
        elif agent == "codex":
            entries.append((project / ".codex" / "skills", Path("..") / ".agents" / "skills"))
        elif agent == "agents":
            continue
        else:
            raise SystemExit(f"未知 Agent: {agent}")
    for entry, target in entries:
        require_allowed_link_target(entry, target, [hub])
        validate_link_destination(entry, target)
    ensure_project_hub(project, execute)
    for entry, target in entries:
        create_symlink(entry, target, execute, args.link_type, allowed_roots=[hub])
    if not execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行")
    return 0


def prepare_link(
    project: Path,
    raw_source: str,
    raw_name: str | None,
    central: Path,
    project_hub: Path,
) -> dict:
    source = expand(raw_source)
    if not any(is_path_inside(source, root) for root in (central, project_hub)):
        raise SystemExit(
            "source 必须位于已配置中央 skills 库或当前项目 skills 库内；"
            f"source={source} central={central} project_hub={project_hub}"
        )
    if not source.is_dir():
        raise SystemExit(f"源路径不存在或不是目录: {source}")
    if not (source / "SKILL.md").is_file():
        raise SystemExit(f"源目录不包含 SKILL.md: {source}")
    name = validate_skill_name(raw_name or source.name)
    if is_path_inside(source, repository_store(central)):
        # A caller may supply a repository subpath, but projects use its stable entry.
        matches = [
            central / skill_name
            for record in read_registry(central)["repositories"].values()
            for skill_name, skill in record["skills"].items()
            if canonical(central / record["path"] / skill["subpath"]) == canonical(source)
        ]
        if len(matches) != 1:
            raise SystemExit(f"仓库内 skill 必须先通过 install-repo 登记中央入口: {source}")
        source = matches[0]
        if not source.is_dir() or not (source / "SKILL.md").is_file():
            raise SystemExit(f"中央入口失效: {source}")
        name = validate_skill_name(raw_name if raw_name is not None else source.name)
    target = project / ".agents" / "skills" / name
    return {
        "source_path": str(source),
        "target_path": str(target),
        "name": name,
    }


def link(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    central = configured_central(project, home, args.library)
    project_hub = project / ".agents" / "skills"
    prepared = prepare_link(project, args.source, args.name, central, project_hub)
    validate_link_destination(Path(prepared["target_path"]), Path(prepared["source_path"]))
    ensure_project_hub(project, args.execute)
    create_symlink(
        Path(prepared["target_path"]),
        Path(prepared["source_path"]),
        args.execute,
        args.link_type,
        allowed_roots=[central, project_hub],
    )
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行")
    return 0


def link_many(args: argparse.Namespace) -> int:
    sources = [part.strip() for part in args.sources.split(",") if part.strip()]
    if not sources:
        raise SystemExit("没有提供可链接的 sources")
    project = expand(args.project)
    home = expand(args.home)
    central = configured_central(project, home, args.library)
    project_hub = project / ".agents" / "skills"
    prepared = [prepare_link(project, raw_source, None, central, project_hub) for raw_source in sources]
    targets = [item["target_path"] for item in prepared]
    if len(set(targets)) != len(targets):
        raise SystemExit("批量链接中存在重复目标名称，已停止")
    for item in prepared:
        validate_link_destination(Path(item["target_path"]), Path(item["source_path"]))
    for item in prepared:
        print(json.dumps({"planned_link": item}, ensure_ascii=False, indent=2))
    ensure_project_hub(project, args.execute)
    for item in prepared:
        create_symlink(
            Path(item["target_path"]),
            Path(item["source_path"]),
            args.execute,
            args.link_type,
            allowed_roots=[central, project_hub],
        )
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行")
    return 0


def project_link_inventory(project: Path, libraries: dict[str, Path]) -> list[dict]:
    hub = project / ".agents" / "skills"
    if not hub.is_dir():
        return []
    result = []
    for entry in sorted(hub.iterdir()):
        if entry.name.startswith(".") or not (entry.is_symlink() or is_junction(entry)):
            continue
        target = immediate_link_target(entry)
        owners = [name for name, central in libraries.items() if is_path_inside(target, central)]
        result.append({"path": str(entry), "immediate_target": str(target), "libraries": owners, "broken": not entry.exists()})
    return result


def check(args: argparse.Namespace) -> int:
    project = expand(args.project)
    home = expand(args.home)
    config = load_effective_config(project, home)
    if config["source"] == "error":
        raise SystemExit(f"中央库配置错误: {config['error']}")
    groups = [("project", project / rel) for rel in PROJECT_SKILL_DIRS]
    if args.include_user:
        groups.extend(("user", path) for path in user_skill_paths(home))
    libraries = {}
    if args.include_central or args.library is not None or args.all_libraries:
        libraries = selected_libraries(project, home, args.library, args.all_libraries)
        groups.extend((f"central:{name}", central) for name, central in libraries.items())
    problems = []
    for name, central in libraries.items():
        try:
            registry = read_registry(central)
        except SystemExit as exc:
            problems.append({"library": name, "directory": str(central), "error": str(exc)})
            continue
        for repo_id, record in registry["repositories"].items():
            try:
                validate_registered_repository(central, record)
            except (SystemExit, subprocess.CalledProcessError) as exc:
                problems.append({"library": name, "repository": repo_id, "directory": str(central), "error": str(exc)})
    for scope, directory in groups:
        directory_state = classify(directory)
        if directory_state["broken"]:
            problem = dict(directory_state)
            problem["name"] = directory.name
            problem["scope"] = scope
            problem["directory"] = str(directory.parent)
            problems.append(problem)
            continue
        if not directory.exists() or not directory.is_dir():
            continue
        for entry in scan_skill_entries(directory):
            if "error" in entry:
                problem = dict(entry)
                problem["scope"] = scope
                problem["directory"] = str(directory)
                problems.append(problem)
                continue
            if entry["broken"] or (entry["is_dir"] and not entry["has_skill_md"]):
                problem = dict(entry)
                problem["scope"] = scope
                problem["directory"] = str(directory)
                problems.append(problem)
    report = {
        "project": str(project),
        "scopes_checked": [scope for scope, _ in groups],
        "problems": problems,
        "project_links": project_link_inventory(project, {
            name: Path(item["path"]) for name, item in config["libraries"].items()
        }),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
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
    if not target.exists() and not item["is_symlink"] and not item["is_junction"]:
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
    if canonical(central) != canonical(expected_central):
        raise SystemExit(f"central 必须等于当前生效配置中的中央库: {expected_central}")
    source_item = classify(source)
    if source_item["is_symlink"] or source_item["is_junction"]:
        raise SystemExit(f"源路径已经是链接，不需要迁移: {source}")
    allowed_source_roots = [project / rel for rel in PROJECT_SKILL_DIRS]
    allowed_source_roots.extend(user_skill_paths(home))
    if not any(is_path_inside(source, root) for root in allowed_source_roots):
        raise SystemExit(
            "source 必须位于当前项目或用户级 Agent skills 目录内；"
            f"source={source} allowed_roots={[str(root) for root in allowed_source_roots]}"
        )
    if not source.is_dir():
        raise SystemExit(f"源路径不存在或不是目录: {source}")
    if not (source / "SKILL.md").is_file():
        raise SystemExit(f"源目录不包含 SKILL.md: {source}")
    name = validate_skill_name(args.name or source.name)
    target = central / name
    if target.exists() or target.is_symlink() or is_junction(target):
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
    try:
        create_symlink(source, target, True, args.link_type, allowed_roots=[expected_central])
    except (OSError, SystemExit):
        shutil.move(str(target), str(source))
        raise
    print(json.dumps({"migrated": plan}, ensure_ascii=False, indent=2))
    return 0


def run_git(repo: Path, command: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *command],
        cwd=repo,
        check=check,
        text=True,
        encoding="utf-8",
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
    branch = run_git(root, ["branch", "--show-current"], check=True).stdout.strip()
    upstream = git_output(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    status = run_git(root, ["status", "--short"], check=True).stdout.strip()
    behind = None
    ahead = None
    if upstream:
        behind = int(run_git(root, ["rev-list", "--count", f"HEAD..{upstream}"], check=True).stdout.strip())
        ahead = int(run_git(root, ["rev-list", "--count", f"{upstream}..HEAD"], check=True).stdout.strip())
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


def registry_tracking_for_repo(repo: Path) -> dict | None:
    root = canonical(repo)
    store = next((parent for parent in root.parents if parent.name == REPOSITORY_DIRNAME), None)
    if store is None:
        return None
    central = store.parent
    if not registry_path(central).exists():
        raise SystemExit(f".repos 中的仓库缺少来源清单: {repo}")
    registry = read_registry(central)
    for repo_id, record in registry["repositories"].items():
        recorded_path = (central / record["path"]).resolve(strict=False)
        if recorded_path == root:
            return {"central": central, "registry": registry, "repo_id": repo_id, "record": record}
    raise SystemExit(f".repos 中的仓库尚未登记，拒绝更新或 checkout: {repo}")


def sync_registry_revision(repo: Path) -> str | None:
    tracking = registry_tracking_for_repo(repo)
    if tracking is None:
        return None
    revision = git_output(repo, ["rev-parse", "HEAD"])
    if revision is None:
        raise SystemExit(f"无法读取仓库 HEAD 以更新来源清单: {repo}")
    tracking["record"]["revision"] = revision
    write_registry(tracking["central"], tracking["registry"])
    return str(registry_path(tracking["central"]))


def validate_registered_repository(central: Path, record: dict, *, check_revision: bool = True) -> Path:
    """Validate provenance and exposed entries before touching a managed repository."""
    repo = central / record["path"]
    if git_root(repo) != canonical(repo):
        raise SystemExit(f"已登记仓库不存在或不是独立 Git 仓库: {repo}")
    origin = run_git(repo, ["remote", "get-url", "origin"], check=True).stdout.strip()
    if origin != record["url"]:
        raise SystemExit(f"仓库 origin 与来源清单不一致: {repo}")
    head = run_git(repo, ["rev-parse", "HEAD"], check=True).stdout.strip()
    if check_revision and head != record["revision"]:
        raise SystemExit(f"仓库 HEAD 与来源清单不一致: {repo}")
    for name, skill in record["skills"].items():
        source = repo / skill["subpath"]
        if not is_path_inside(source, repo):
            raise SystemExit(f"已登记 skill 越出仓库: {source}")
        if read_skill_name(source) != name:
            raise SystemExit(f"已登记 skill 名称发生变化: {source}")
        if validate_link_destination(central / skill["entry"], source) != "same-link":
            raise SystemExit(f"已登记中央入口缺失: {central / skill['entry']}")
    return repo


def find_git_repos(path: Path) -> list[Path]:
    """The registry is authoritative; unregistered directories are never fetched."""
    return [validate_registered_repository(path, record) for record in read_registry(path)["repositories"].values()]


def revision_skill_files(repo: Path, revision: str) -> dict[str, str]:
    files = run_git(repo, ["ls-tree", "-r", "-z", revision], check=True).stdout
    return {
        path: metadata.split()[0]
        for item in files.split("\0") if item
        for metadata, path in [item.split("\t", 1)]
        if Path(path).name == "SKILL.md"
    }


def revision_impact(repo: Path, revision: str, record: dict) -> dict:
    """Inspect Git objects without checking out unvalidated upstream content."""
    before = revision_skill_files(repo, "HEAD")
    after = revision_skill_files(repo, revision)
    changed = run_git(repo, ["diff", "--name-only", "-z", "HEAD", revision, "--"], check=True).stdout
    changed_files = [path for path in changed.split("\0") if path]
    invalid = []
    affected = []
    registered = set()
    for name, skill in record["skills"].items():
        subpath = skill["subpath"]
        skill_file = (Path(subpath) / "SKILL.md").as_posix()
        registered.add(skill_file)
        if skill_file not in after:
            invalid.append({"skill": name, "error": "SKILL.md 被删除或移动", "path": skill_file})
        elif after[skill_file] != "100644" and after[skill_file] != "100755":
            invalid.append({"skill": name, "error": "SKILL.md 不是普通 Git 文件", "path": skill_file})
        else:
            text = run_git(repo, ["show", f"{revision}:{skill_file}"], check=True).stdout
            try:
                actual_name = parse_skill_name(text, f"{revision}:{skill_file}")
                if actual_name != name:
                    invalid.append({"skill": name, "error": f"name 已变为 {actual_name}", "path": skill_file})
            except SystemExit as exc:
                invalid.append({"skill": name, "error": str(exc), "path": skill_file})
        if (subpath == "." and changed_files) or any(path.startswith(subpath + "/") for path in changed_files):
            affected.append(name)
    return {
        "candidate_revision": revision,
        "changed_files": changed_files,
        "directly_changed_skills": affected,
        "added_skill_files": sorted(set(after) - set(before)),
        "removed_skill_files": sorted(set(before) - set(after)),
        "available_skill_files": sorted(set(after) - registered),
        "invalid_registered_skills": invalid,
        "shared_resource_note": "仓库共享资源可能影响未直接修改的 skills；此处列出全部变更文件。",
    }


def git_status(args: argparse.Namespace) -> int:
    repo = expand(args.repo)
    print(json.dumps(git_status_dict(repo), ensure_ascii=False, indent=2))
    return 0


def updates(args: argparse.Namespace) -> int:
    libraries = selected_libraries(expand(args.project), expand(args.home), args.library, args.all_libraries)
    reports = []
    errors = []
    for name, central in libraries.items():
        registry = read_registry(central)
        for repo_id, record in registry["repositories"].items():
            try:
                repo = validate_registered_repository(central, record)
            except (SystemExit, subprocess.CalledProcessError) as exc:
                errors.append({"library": name, "repository": repo_id, "error": str(exc)})
                continue
            report = {"library": name, "repository": repo_id, "central": str(central)}
            if args.execute:
                result = run_git(repo, ["fetch", "--prune"])
                if result.returncode != 0:
                    # Never present stale ahead/behind values as a successful remote check.
                    report.update({"freshness": "fetch-failed", "update_state": "unknown", "error": result.stderr.strip()})
                    errors.append(report)
                    reports.append(report)
                    continue
            status = git_status_dict(repo)
            report.update(status)
            report["freshness"] = "fetched" if args.execute else "local-cache"
            if status["behind"] is None:
                report["update_state"] = "unknown"
            else:
                report["update_state"] = (
                    "diverged" if status["behind"] and status["ahead"] else
                    "update-available" if status["behind"] else
                    "ahead" if status["ahead"] else "up-to-date"
                )
                revision = run_git(repo, ["rev-parse", status["upstream"]], check=True).stdout.strip()
                report["impact"] = revision_impact(repo, revision, record)
            reports.append(report)
    print(json.dumps({
        "libraries": {name: str(path) for name, path in libraries.items()},
        "remote_checked": args.execute,
        "note": "fetched 表示本次 fetch 成功时的远端状态；local-cache 不能用于判断 GitHub 最新状态。",
        "repositories": reports,
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def update_repo(args: argparse.Namespace) -> int:
    repo = expand(args.repo)
    status = git_status_dict(repo)
    if not status["is_git_repo"]:
        raise SystemExit(f"不是 git 仓库: {repo}")
    tracking = registry_tracking_for_repo(Path(status["path"]))
    if args.library is not None:
        central = configured_central(expand(args.project), expand(args.home), args.library)
        if tracking is None or canonical(tracking["central"]) != canonical(central):
            raise SystemExit("--repo 不属于指定中央库的已登记仓库")
    if tracking is not None:
        validate_registered_repository(tracking["central"], tracking["record"])
    plan = {
        "repository": status,
        "registry_update": str(registry_path(tracking["central"])) if tracking is not None else None,
    }
    print(json.dumps({"planned_update": plan}, ensure_ascii=False, indent=2))
    if status["dirty"]:
        raise SystemExit("仓库有本地改动；请先处理改动再更新")
    if status["upstream"] is None:
        raise SystemExit("当前分支没有 upstream；拒绝更新")
    if status["branch"] is None or status["branch"] == "":
        raise SystemExit("当前仓库处于 detached HEAD；拒绝更新")
    if not args.execute:
        print("当前只是 dry-run；--execute 会 fetch、验证候选版本，并 fast-forward 到该提交")
        return 0
    root = Path(status["path"])
    fetch = run_git(root, ["fetch", "--prune"])
    if fetch.returncode != 0:
        raise SystemExit(fetch.stderr.strip())
    revision = run_git(root, ["rev-parse", "@{u}"], check=True).stdout.strip()
    head = run_git(root, ["rev-parse", "HEAD"], check=True).stdout.strip()
    ancestor = run_git(root, ["merge-base", "--is-ancestor", head, revision])
    if ancestor.returncode != 0:
        raise SystemExit("本地 HEAD 不是远端提交的祖先，拒绝更新；请处理本地提交或分叉")
    if tracking is not None:
        impact = revision_impact(root, revision, tracking["record"])
        print(json.dumps({"impact": impact}, ensure_ascii=False, indent=2))
        if impact["invalid_registered_skills"]:
            raise SystemExit("候选版本破坏已登记 skill；工作区未更新，请先审查入口迁移计划")
    # Apply exactly the inspected object; a second network fetch could change it.
    run_git(root, ["merge", "--ff-only", revision], check=True)
    if tracking is not None:
        validate_registered_repository(tracking["central"], tracking["record"], check_revision=False)
    updated_registry = sync_registry_revision(root)
    print(
        json.dumps(
            {"updated": git_status_dict(root), "updated_registry": updated_registry},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def checkout(args: argparse.Namespace) -> int:
    repo = expand(args.repo)
    checkout_ref = validate_git_argument(args.ref, "checkout ref")
    status = git_status_dict(repo)
    if not status["is_git_repo"]:
        raise SystemExit(f"不是 git 仓库: {repo}")
    tracking = registry_tracking_for_repo(Path(status["path"]))
    plan = {
        "repo": status,
        "checkout_ref": checkout_ref,
        "registry_update": str(registry_path(tracking["central"])) if tracking is not None else None,
    }
    print(json.dumps({"planned_checkout": plan}, ensure_ascii=False, indent=2))
    if status["dirty"] and not args.allow_dirty:
        raise SystemExit("仓库有本地改动；默认不切换版本。确认要继续时传入 --allow-dirty")
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行 git checkout")
        return 0
    root = Path(status["path"])
    result = run_git(root, ["checkout", checkout_ref])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip())
    updated_registry = sync_registry_revision(root)
    print(result.stdout.strip())
    print(
        json.dumps(
            {"checked_out": git_status_dict(root), "updated_registry": updated_registry},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def clone(args: argparse.Namespace) -> int:
    dest_parent = expand(args.dest_parent)
    repo_url = validate_git_argument(args.repo_url, "repo URL")
    inferred_name = Path(repo_url.rstrip("/").removesuffix(".git")).name
    repo_name = validate_directory_name(args.name or inferred_name, "仓库目录名")
    dest = dest_parent / repo_name
    plan = {
        "repo_url": repo_url,
        "destination": str(dest),
        "after_clone_detection": [
            "检查仓库根目录是否包含 SKILL.md",
            "检查 skills/*/SKILL.md",
            "检查 .agents/skills/*/SKILL.md",
        ],
    }
    print(json.dumps({"planned_clone": plan}, ensure_ascii=False, indent=2))
    if path_lexists(dest):
        raise SystemExit(f"目标路径已存在，默认不覆盖: {dest}")
    if not args.execute:
        print("当前只是 dry-run；用户确认后再传入 --execute 执行 git clone")
        return 0
    dest_parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--", repo_url, str(dest)],
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
    agents = [part.strip() for part in raw.split(",") if part.strip()]
    allowed = {"agents", "codex", "claude"}
    unknown = set(agents).difference(allowed)
    if unknown:
        raise SystemExit(f"未知 Agent: {sorted(unknown)}")
    if len(agents) != len(set(agents)):
        raise SystemExit("Agent 列表不能包含重复项")
    if not agents:
        raise SystemExit("至少需要指定一个 Agent")
    return agents


def main() -> int:
    parser = argparse.ArgumentParser(description="安全管理 Agent skills 的中央库与项目级入口。")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
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
    config_parser.add_argument("--library", default=DEFAULT_LIBRARY_NAME)
    config_parser.add_argument("--mode", choices=sorted(VALID_DEFAULT_MODES), default="centralize")
    config_parser.add_argument("--allow-global-central", action="store_true")
    config_parser.add_argument("--allow-non-namespaced-central", action="store_true")
    config_parser.add_argument("--execute", action="store_true")
    config_parser.set_defaults(func=config)

    migrate_config_parser = sub.add_parser("migrate-config")
    migrate_config_parser.add_argument("--project", default=".")
    migrate_config_parser.add_argument("--home", default="~")
    migrate_config_parser.add_argument("--scope", choices=["project", "user"], default="user")
    migrate_config_parser.add_argument("--library", default=DEFAULT_LIBRARY_NAME)
    migrate_config_parser.add_argument("--allow-global-central", action="store_true")
    migrate_config_parser.add_argument("--allow-non-namespaced-central", action="store_true")
    migrate_config_parser.add_argument("--execute", action="store_true")
    migrate_config_parser.set_defaults(func=migrate_config)

    library_list_parser = sub.add_parser("library-list")
    library_list_parser.add_argument("--project", default=".")
    library_list_parser.add_argument("--home", default="~")
    library_list_parser.set_defaults(func=library_list)

    library_add_parser = sub.add_parser("library-add")
    library_add_parser.add_argument("--project", default=".")
    library_add_parser.add_argument("--home", default="~")
    library_add_parser.add_argument("--scope", choices=["project", "user"], default="user")
    library_add_parser.add_argument("--name", required=True)
    library_add_parser.add_argument("--central")
    library_add_parser.add_argument("--central-base")
    library_add_parser.add_argument("--activate", action="store_true")
    library_add_parser.add_argument("--allow-global-central", action="store_true")
    library_add_parser.add_argument("--allow-non-namespaced-central", action="store_true")
    library_add_parser.add_argument("--execute", action="store_true")
    library_add_parser.set_defaults(func=library_add)

    library_use_parser = sub.add_parser("library-use")
    library_use_parser.add_argument("--project", default=".")
    library_use_parser.add_argument("--home", default="~")
    library_use_parser.add_argument("--scope", choices=["project", "user"], default="user")
    library_use_parser.add_argument("--name", required=True)
    library_use_parser.add_argument("--execute", action="store_true")
    library_use_parser.set_defaults(func=library_use)

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
    link_parser.add_argument("--library")
    link_parser.add_argument("--source", required=True)
    link_parser.add_argument("--name")
    link_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    link_parser.add_argument("--execute", action="store_true")
    link_parser.set_defaults(func=link)

    link_many_parser = sub.add_parser("link-many")
    link_many_parser.add_argument("--project", default=".")
    link_many_parser.add_argument("--home", default="~")
    link_many_parser.add_argument("--library")
    link_many_parser.add_argument("--sources", required=True)
    link_many_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    link_many_parser.add_argument("--execute", action="store_true")
    link_many_parser.set_defaults(func=link_many)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--project", default=".")
    check_parser.add_argument("--home", default="~")
    check_parser.add_argument("--include-user", action="store_true")
    check_parser.add_argument("--include-central", action="store_true")
    check_libraries = check_parser.add_mutually_exclusive_group()
    check_libraries.add_argument("--library")
    check_libraries.add_argument("--all-libraries", action="store_true")
    check_parser.set_defaults(func=check)

    unlink_parser = sub.add_parser("unlink")
    unlink_parser.add_argument("--target", required=True)
    unlink_parser.add_argument("--execute", action="store_true")
    unlink_parser.set_defaults(func=unlink)

    git_status_parser = sub.add_parser("git-status")
    git_status_parser.add_argument("--repo", required=True)
    git_status_parser.set_defaults(func=git_status)

    updates_parser = sub.add_parser("updates")
    update_libraries = updates_parser.add_mutually_exclusive_group()
    update_libraries.add_argument("--library")
    update_libraries.add_argument("--all-libraries", action="store_true")
    updates_parser.add_argument("--project", default=".")
    updates_parser.add_argument("--home", default="~")
    updates_parser.add_argument("--execute", action="store_true")
    updates_parser.set_defaults(func=updates)

    update_parser = sub.add_parser("update")
    update_parser.add_argument("--repo", required=True)
    update_parser.add_argument("--project", default=".")
    update_parser.add_argument("--home", default="~")
    update_parser.add_argument("--library")
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

    install_repo_parser = sub.add_parser("install-repo")
    install_repo_parser.add_argument("--project", default=".")
    install_repo_parser.add_argument("--home", default="~")
    install_repo_parser.add_argument("--library")
    install_repo_parser.add_argument("--repo-url", required=True)
    install_repo_parser.add_argument("--skills", required=True)
    install_repo_parser.add_argument("--enable-project", action="store_true")
    install_repo_parser.add_argument("--link-type", choices=["auto", "symlink", "junction"], default="auto")
    install_repo_parser.add_argument("--execute", action="store_true")
    install_repo_parser.set_defaults(func=install_repo)

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
