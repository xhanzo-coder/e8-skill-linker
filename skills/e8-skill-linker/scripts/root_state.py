"""Schema v3: one user root, a fixed central library, explicit project bindings.

Only metadata is managed here. Skill contents and links remain the responsibility
of skill_manager. Reads never initialize missing directories or repair identities.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

SCHEMA = 3
CONFIG = ".skill-linker.json"
CATALOG = ".skill-linker-registry.json"
MARKER = ".skill-linker-library.json"
MAIN = "central"


def absolute(value: str | Path) -> Path:
    return Path(value).expanduser().absolute()


def plain_location(path: Path) -> None:
    if path.resolve(strict=False) != path.absolute() or path.is_symlink():
        raise ValueError(f"管理路径或父目录包含链接，需先审查: {path}")


def exact(data: object, fields: set[str], label: str) -> None:
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(f"{label} 字段必须为 {sorted(fields)}；不接受缺失或未知字段")


def identity(value: str) -> None:
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError("身份必须是规范 UUID")


def name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) or len(value) > 64:
        raise ValueError("名称必须为 1-64 位小写字母、数字或单个连字符分隔的片段")
    if value in {"con", "prn", "aux", "nul", *[f"com{i}" for i in range(1, 10)], *[f"lpt{i}" for i in range(1, 10)]}:
        raise ValueError("名称不能是 Windows 保留设备名")
    return value


def read_json(path: Path) -> dict:
    plain_location(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是 object: {path}")
    return value


def encode(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def metadata_snapshot(path: Path, parsed: dict) -> bytes:
    """Never pair stale parsed data with a newer optimistic-lock byte snapshot."""
    plain_location(path)
    content = path.read_bytes()
    if json.loads(content.decode("utf-8")) != parsed:
        raise ValueError(f"元数据在读取后变化，重新制定计划: {path}")
    return content


def atomic_bytes(path: Path, content: bytes) -> None:
    plain_location(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".skill-linker-write-", delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def root_lock(root: Path):
    """Exclusive cooperative writer lock. A stale lock requires explicit inspection."""
    lock = root / ".skill-linker-write.lock"
    plain_location(lock)
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    try:
        yield
    finally:
        lock.unlink()


def commit_metadata(root: Path, changes: dict[Path, dict], expected: dict[Path, bytes | None]) -> None:
    """Reject stale state; recover ordinary write failures without swallowing them."""
    if set(changes) != set(expected):
        raise ValueError("每个元数据写入必须提供执行前状态")
    with root_lock(root):
        for path, before in expected.items():
            plain_location(path)
            current = path.read_bytes() if path.exists() else None
            if current != before:
                raise ValueError(f"元数据在预检后变化，重新制定计划: {path}")
        completed = []
        try:
            for path, data in changes.items():
                atomic_bytes(path, encode(data))
                completed.append(path)
        except OSError:
            for path in reversed(completed):
                if expected[path] is None:
                    path.unlink()
                else:
                    atomic_bytes(path, expected[path])
            raise


def validate_root_location(root: Path, home: Path, project: Path) -> None:
    plain_location(root)
    if root == Path(root.anchor) or root in {home, project}:
        raise ValueError("管理根不能是盘符根、用户目录或项目根本身")
    for base in (home, project):
        for rel in (".agents/skills", ".codex/skills", ".claude/skills"):
            discovery = (base / rel).resolve(strict=False)
            if root == discovery or discovery in root.parents or root in discovery.parents:
                raise ValueError("管理根不能与 Agent 发现目录重叠")


def new_catalog() -> dict:
    return {"schema_version": SCHEMA, "root_id": str(uuid.uuid4()),
            "libraries": {MAIN: {"path": f"libraries/{MAIN}", "library_id": str(uuid.uuid4())}},
            "projects": {}}


def library_marker(catalog: dict, library: str) -> dict:
    return {"schema_version": SCHEMA, "root_id": catalog["root_id"], "name": library,
            "library_id": catalog["libraries"][library]["library_id"]}


def read_catalog(root: Path) -> dict:
    data = read_json(root / CATALOG)
    exact(data, {"schema_version", "root_id", "libraries", "projects"}, "管理登记表")
    if data["schema_version"] != SCHEMA:
        raise ValueError("管理登记表 schema_version 必须为 3")
    identity(data["root_id"])
    if not isinstance(data["libraries"], dict) or MAIN not in data["libraries"]:
        raise ValueError("管理登记表必须包含固定中央主库 central")
    ids = set()
    for library, record in data["libraries"].items():
        name(library)
        exact(record, {"path", "library_id"}, "库记录")
        identity(record["library_id"])
        if record["library_id"] in ids:
            raise ValueError("库身份重复")
        ids.add(record["library_id"])
        if record["path"] != f"libraries/{library}":
            raise ValueError("库必须位于管理根 libraries/<库名>，不接受路径越界或外部库")
        directory = root / record["path"]
        plain_location(directory)
        if not directory.is_dir() or read_json(directory / MARKER) != library_marker(data, library):
            raise ValueError(f"库目录缺失或身份不符: {directory}")
    if not isinstance(data["projects"], dict):
        raise ValueError("projects 必须是 object")
    paths = set()
    for project_id, record in data["projects"].items():
        identity(project_id)
        exact(record, {"path"}, "项目登记")
        path = Path(record["path"])
        if not path.is_absolute() or path != path.resolve(strict=False) or path in paths:
            raise ValueError("已登记项目必须使用唯一规范绝对路径")
        paths.add(path)
    return data


def read_user(home: Path) -> tuple[Path, dict]:
    data = read_json(home / CONFIG)
    if "schema_version" not in data or data["schema_version"] != SCHEMA:
        raise ValueError("旧配置不能直接运行；先使用 migrate-config 显式迁移到 schema v3")
    exact(data, {"schema_version", "root", "root_id"}, "用户配置")
    identity(data["root_id"])
    root = Path(data["root"])
    if not root.is_absolute():
        raise ValueError("管理根必须是绝对路径")
    plain_location(root)
    validate_root_location(root, home, home)
    catalog = read_catalog(root)
    if catalog["root_id"] != data["root_id"]:
        raise ValueError("root_id 不匹配；拒绝连接另一个管理根")
    return root, catalog


def read_binding(project: Path, catalog: dict) -> dict | None:
    path = project / CONFIG
    plain_location(path)
    if not path.exists():
        if any(Path(item["path"]) == project for item in catalog["projects"].values()):
            raise ValueError("项目已登记但绑定文件缺失；需显式修复")
        return None
    data = read_json(path)
    if "schema_version" not in data or data["schema_version"] != SCHEMA:
        raise ValueError("项目旧配置不能覆盖库清单；使用 project-bind --replace-v2 显式迁移")
    exact(data, {"schema_version", "root_id", "project_id", "default_library", "enabled"}, "项目绑定")
    identity(data["project_id"])
    if data["root_id"] != catalog["root_id"]:
        raise ValueError("项目绑定到另一个管理根，停止，不自动合并")
    if data["project_id"] not in catalog["projects"] or Path(catalog["projects"][data["project_id"]]["path"]) != project:
        raise ValueError("项目身份与登记路径不符；移动或复制后使用 project-rebind")
    if data["default_library"] not in catalog["libraries"]:
        raise ValueError("项目默认库不存在；不会自动换成 central")
    if not isinstance(data["enabled"], dict):
        raise ValueError("enabled 必须是 object")
    for skill, library in data["enabled"].items():
        name(skill)
        if library not in catalog["libraries"]:
            raise ValueError(f"启用项引用了不存在的库: {skill}")
    return data


def load_effective_config(project: Path, home: Path) -> dict:
    """Diagnostic projection used by inventory and commands; errors remain explicit."""
    paths = {"project": str(project / CONFIG), "user": str(home / CONFIG)}
    try:
        plain_location(home / CONFIG)
        if not (home / CONFIG).exists():
            if (project / CONFIG).exists():
                raise ValueError("有项目绑定但没有用户管理根指针；先显式连接正确的管理根")
            return {"source": None, "path": None, "libraries": {}, "active_library": None,
                    "central_skills_dir": None, "central_exists": False, "search_paths": paths,
                    "root": None, "binding": None}
        root, catalog = read_user(home)
        validate_root_location(root, home, project)
        binding = read_binding(project, catalog)
        active = MAIN if binding is None else binding["default_library"]
        libraries = {key: {"path": str(root / item["path"]), "exists": True,
                           "library_id": item["library_id"]} for key, item in catalog["libraries"].items()}
        return {"source": "user-root", "path": str(home / CONFIG), "schema_version": SCHEMA,
                "root": str(root), "root_id": catalog["root_id"], "catalog": catalog,
                "binding": binding, "libraries": libraries, "active_library": active,
                "central_skills_dir": libraries[active]["path"], "central_exists": True,
                "search_paths": paths}
    except (OSError, ValueError) as exc:
        return {"source": "error", "path": str(home / CONFIG), "error": str(exc), "search_paths": paths}


def project_directory(raw: str) -> Path:
    path = absolute(raw)
    if not path.is_dir():
        raise ValueError(f"项目根目录不存在: {path}")
    plain_location(path)
    return path


def root_init(args: argparse.Namespace) -> int:
    home, project, root = absolute(args.home), project_directory(args.project), absolute(args.root)
    validate_root_location(root, home, project)
    pointer = home / CONFIG
    plain_location(pointer)
    if pointer.exists():
        raise ValueError("用户配置已存在；使用 root-connect 或 migrate-config，不覆盖")
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("目标目录非空；已有合法登记表用 root-connect，其他内容先审查")
    data = new_catalog()
    central = root / "libraries" / MAIN
    print(json.dumps({"root": str(root), "primary_library": MAIN, "central": str(central),
                      "user_config": str(pointer), "migrate_existing": False}, ensure_ascii=False, indent=2))
    if args.execute:
        central.mkdir(parents=True)
        home.mkdir(parents=True, exist_ok=True)
        commit_metadata(root, {central / MARKER: library_marker(data, MAIN), root / CATALOG: data,
                              pointer: {"schema_version": SCHEMA, "root": str(root), "root_id": data["root_id"]}},
                        {central / MARKER: None, root / CATALOG: None, pointer: None})
    return 0


def root_connect(args: argparse.Namespace) -> int:
    home, project, root = absolute(args.home), project_directory(args.project), absolute(args.root)
    validate_root_location(root, home, project)
    catalog = read_catalog(root)
    # A foreign project binding must not be silently connected to another root.
    read_binding(project, catalog)
    pointer = home / CONFIG
    plain_location(pointer)
    before = pointer.read_bytes() if pointer.exists() else None
    desired = {"schema_version": SCHEMA, "root": str(root), "root_id": catalog["root_id"]}
    if before is not None and read_json(pointer) != desired:
        raise ValueError("用户指针已指向其他状态；先审查迁移，不覆盖")
    print(json.dumps({"connect_root": str(root), "root_id": catalog["root_id"],
                      "user_config": str(pointer), "libraries": catalog["libraries"]}, ensure_ascii=False, indent=2))
    if args.execute:
        if args.expected_root_id != catalog["root_id"]:
            raise ValueError("连接必须携带计划中的 --expected-root-id；它不是用户批准令牌")
        home.mkdir(parents=True, exist_ok=True)
        commit_metadata(root, {pointer: desired}, {pointer: before})
    return 0


def library_add(args: argparse.Namespace) -> int:
    home = absolute(args.home)
    project = project_directory(args.project)
    root, catalog = read_user(home)
    validate_root_location(root, home, project)
    library = name(args.name)
    if library == MAIN or library in catalog["libraries"]:
        raise ValueError("central 是固定主库；该库名已存在或保留")
    catalog_path = root / CATALOG
    # Preserve the exact original bytes for optimistic checks and rollback.
    before = metadata_snapshot(catalog_path, catalog)
    target = root / "libraries" / library
    plain_location(target)
    if target.exists():
        raise ValueError("目标库目录已存在但未登记；先审查，不接管")
    catalog["libraries"][library] = {"path": f"libraries/{library}", "library_id": str(uuid.uuid4())}
    print(json.dumps({"add_library": library, "path": str(target), "change_project_default": False}, ensure_ascii=False, indent=2))
    if args.execute:
        target.mkdir()
        try:
            commit_metadata(root, {target / MARKER: library_marker(catalog, library), catalog_path: catalog},
                            {target / MARKER: None, catalog_path: before})
        except (OSError, ValueError):
            if not any(target.iterdir()):
                target.rmdir()
            raise
    return 0


def project_bind(args: argparse.Namespace) -> int:
    home, project = absolute(args.home), project_directory(args.project)
    root, catalog = read_user(home)
    validate_root_location(root, home, project)
    path = project / CONFIG
    plain_location(path)
    if args.library not in catalog["libraries"]:
        raise ValueError("选定的默认库未登记")
    old = path.read_bytes() if path.exists() else None
    backup = project / ".skill-linker-v2-config.backup.json"
    if old is not None:
        previous = read_json(path)
        if not args.replace_v2 or previous["schema_version"] != 2:
            raise ValueError("项目配置已存在；修改默认库用 library-use，复制/移动用 project-rebind")
        exact(previous, {"schema_version", "libraries", "active_library", "default_mode"}, "v2 项目配置")
        plain_location(backup)
        if backup.exists():
            raise ValueError("旧项目配置备份已存在，不覆盖")
    if any(Path(item["path"]) == project for item in catalog["projects"].values()):
        raise ValueError("该项目路径已登记；先审查缺失或冲突的绑定")
    project_id = str(uuid.uuid4())
    binding = {"schema_version": SCHEMA, "root_id": catalog["root_id"], "project_id": project_id,
               "default_library": args.library, "enabled": {}}
    catalog_before = metadata_snapshot(root / CATALOG, catalog)
    catalog["projects"][project_id] = {"path": str(project)}
    print(json.dumps({"bind_project": str(project), "default_library": args.library,
                      "project_config": str(path), "existing_entries_unchanged": True,
                      "backup": str(backup) if old is not None else None}, ensure_ascii=False, indent=2))
    if args.execute:
        changes = {path: binding, root / CATALOG: catalog}
        expected = {path: old, root / CATALOG: catalog_before}
        if old is not None:
            changes[backup] = previous
            expected[backup] = None
        commit_metadata(root, changes, expected)
    return 0


def library_use(args: argparse.Namespace) -> int:
    project, home = project_directory(args.project), absolute(args.home)
    root, catalog = read_user(home)
    validate_root_location(root, home, project)
    binding = read_binding(project, catalog)
    if binding is None:
        raise ValueError("项目尚未绑定；先运行 project-bind")
    if args.name not in catalog["libraries"]:
        raise ValueError("选定库不存在，不切换")
    path = project / CONFIG
    before = metadata_snapshot(path, binding)
    old = binding["default_library"]
    binding["default_library"] = args.name
    print(json.dumps({"project": str(project), "from": old, "to": args.name,
                      "enabled_unchanged": binding["enabled"], "relink": False}, ensure_ascii=False, indent=2))
    if args.execute:
        commit_metadata(root, {path: binding}, {path: before})
    return 0


def project_rebind(args: argparse.Namespace) -> int:
    home, project = absolute(args.home), project_directory(args.project)
    root, catalog = read_user(home)
    validate_root_location(root, home, project)
    path = project / CONFIG
    binding = read_json(path)
    exact(binding, {"schema_version", "root_id", "project_id", "default_library", "enabled"}, "项目绑定")
    if binding["schema_version"] != SCHEMA or binding["root_id"] != catalog["root_id"]:
        raise ValueError("项目不是当前管理根的 v3 绑定")
    previous_path = Path(catalog["projects"][binding["project_id"]]["path"])
    if previous_path == project or any(Path(item["path"]) == project for item in catalog["projects"].values()):
        raise ValueError("当前项目路径已登记，无需重新绑定")
    if args.mode == "move" and previous_path.exists():
        raise ValueError("原项目路径仍存在；不能当作移动，可显式选择 copy")
    before = {path: metadata_snapshot(path, binding), root / CATALOG: metadata_snapshot(root / CATALOG, catalog)}
    if args.mode == "copy":
        binding["project_id"] = str(uuid.uuid4())
    catalog["projects"][binding["project_id"]] = {"path": str(project)}
    # Validate the proposed binding against the new registry before changing anything.
    if binding["default_library"] not in catalog["libraries"] or not isinstance(binding["enabled"], dict):
        raise ValueError("复制/移动的绑定含无效默认库或启用清单")
    for skill, library in binding["enabled"].items():
        name(skill)
        if library not in catalog["libraries"]:
            raise ValueError("复制/移动的绑定引用不存在的库")
    print(json.dumps({"mode": args.mode, "from": str(previous_path), "to": str(project),
                      "project_id": binding["project_id"], "links_unchanged": True}, ensure_ascii=False, indent=2))
    if args.execute:
        commit_metadata(root, {path: binding, root / CATALOG: catalog}, before)
    return 0


def config(args: argparse.Namespace) -> int:
    report = load_effective_config(project_directory(args.project), absolute(args.home))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["source"] == "error")


def add_commands(sub) -> None:
    """Define the v3 management surface; old write flags are deliberately rejected."""
    handlers = {"config": config, "library-list": config, "root-init": root_init,
                "root-connect": root_connect, "library-add": library_add,
                "project-bind": project_bind, "library-use": library_use, "project-rebind": project_rebind}
    for command, handler in handlers.items():
        parser = sub.add_parser(command)
        parser.add_argument("--project", default=".")
        parser.add_argument("--home", default="~")
        if command not in {"config", "library-list"}:
            parser.add_argument("--execute", action="store_true")
        if command in {"root-init", "root-connect"}:
            parser.add_argument("--root", required=True)
        if command == "root-connect":
            parser.add_argument("--expected-root-id")
        if command in {"library-add", "library-use"}:
            parser.add_argument("--name", required=True)
        if command == "project-bind":
            parser.add_argument("--library", default=MAIN)
            parser.add_argument("--replace-v2", action="store_true")
        if command == "project-rebind":
            parser.add_argument("--mode", choices=["move", "copy"], required=True)
        parser.set_defaults(func=handler)
