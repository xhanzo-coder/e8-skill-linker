"""Schema v3 identity, project graph and migration tests; isolated files only."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import uuid

from test_skill_manager import skill_manager as manager, write_skill, init_git_repo

state = manager.root_state


class RootStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.project = self.base / "项目 A"
        self.root = self.base / "SkillsHub"
        self.home.mkdir()
        self.project.mkdir()
        self.link_type = "junction" if os.name == "nt" else "symlink"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, command: str, *flags: str) -> tuple[int, str]:
        argv = ["skill_manager.py", command, "--home", str(self.home), "--project", str(self.project), *flags]
        output = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            code = manager.main()
        return code, output.getvalue()

    def initialize(self, bind: bool = True) -> Path:
        self.cli("root-init", "--root", str(self.root), "--execute")
        if bind:
            self.cli("project-bind", "--execute")
        return self.root / "libraries" / "central"

    def json_write(self, path: Path, data: dict) -> None:
        path.write_bytes(state.encode(data))

    def catalog(self) -> dict:
        return state.read_json(self.root / state.CATALOG)

    def binding(self) -> dict:
        return state.read_json(self.project / state.CONFIG)

    def test_init_dry_run_creates_nothing(self) -> None:
        self.cli("root-init", "--root", str(self.root))
        self.assertFalse(self.root.exists())
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertEqual(list(self.project.iterdir()), [])

    def test_fixed_primary_and_identity_markers(self) -> None:
        central = self.initialize(False)
        pointer = state.read_json(self.home / state.CONFIG)
        catalog = state.read_catalog(self.root)
        self.assertEqual(set(catalog["libraries"]), {"central"})
        self.assertEqual(pointer["root_id"], catalog["root_id"])
        self.assertEqual(state.read_json(central / state.MARKER), state.library_marker(catalog, "central"))
        self.assertEqual(manager.load_effective_config(self.project, self.home)["active_library"], "central")
        self.assertFalse((self.project / state.CONFIG).exists())

    def test_existing_config_is_not_overwritten_by_init(self) -> None:
        self.initialize()
        before = (self.home / state.CONFIG).read_bytes()
        with self.assertRaisesRegex(ValueError, "已存在"):
            self.cli("root-init", "--root", str(self.base / "second"), "--execute")
        self.assertEqual((self.home / state.CONFIG).read_bytes(), before)

    def test_project_bind_rejects_management_root_as_project(self) -> None:
        self.initialize(False)
        self.project = self.root
        before = (self.root / state.CATALOG).read_bytes()
        with self.assertRaisesRegex(ValueError, "项目根本身"):
            self.cli("project-bind", "--execute")
        self.assertFalse((self.root / state.CONFIG).exists())
        self.assertEqual((self.root / state.CATALOG).read_bytes(), before)

    def test_unknown_nonempty_folder_is_not_adopted(self) -> None:
        self.root.mkdir()
        (self.root / "central").mkdir()
        with self.assertRaisesRegex(ValueError, "非空"):
            self.cli("root-init", "--root", str(self.root), "--execute")
        with self.assertRaises(FileNotFoundError):
            self.cli("root-connect", "--root", str(self.root))
        self.assertFalse((self.home / state.CONFIG).exists())

    def test_connect_requires_reviewed_root_id_and_preserves_libraries(self) -> None:
        self.initialize(False)
        (self.home / state.CONFIG).unlink()
        _, output = self.cli("root-connect", "--root", str(self.root))
        root_id = json.loads(output)["root_id"]
        with self.assertRaisesRegex(ValueError, "expected-root-id"):
            self.cli("root-connect", "--root", str(self.root), "--execute")
        self.assertFalse((self.home / state.CONFIG).exists())
        self.cli("root-connect", "--root", str(self.root), "--expected-root-id", root_id, "--execute")
        self.assertEqual(state.read_user(self.home)[1]["root_id"], root_id)

    def test_tampered_root_id_is_not_a_new_library(self) -> None:
        self.initialize()
        pointer = state.read_json(self.home / state.CONFIG)
        pointer["root_id"] = str(uuid.uuid4())
        self.json_write(self.home / state.CONFIG, pointer)
        report = manager.load_effective_config(self.project, self.home)
        self.assertEqual(report["source"], "error")
        self.assertIn("root_id", report["error"])

    def test_missing_root_stops_without_recreation(self) -> None:
        self.initialize()
        moved = self.base / "offline-root"
        self.root.rename(moved)
        code, output = self.cli("config")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["source"], "error")
        self.assertFalse(self.root.exists())

    def test_library_marker_mismatch_stops_selection(self) -> None:
        central = self.initialize()
        marker = state.read_json(central / state.MARKER)
        marker["library_id"] = str(uuid.uuid4())
        self.json_write(central / state.MARKER, marker)
        with self.assertRaisesRegex(SystemExit, "身份不符"):
            manager.configured_central(self.project, self.home)

    def test_catalog_cannot_omit_or_relocate_primary(self) -> None:
        self.initialize()
        catalog = self.catalog()
        catalog["libraries"]["central"]["path"] = "../outside"
        self.json_write(self.root / state.CATALOG, catalog)
        with self.assertRaisesRegex(ValueError, "路径越界"):
            state.read_user(self.home)
        del catalog["libraries"]["central"]
        self.json_write(self.root / state.CATALOG, catalog)
        with self.assertRaisesRegex(ValueError, "固定中央主库"):
            state.read_user(self.home)

    def test_library_add_uses_only_name_and_reserved_main(self) -> None:
        self.initialize()
        self.cli("library-add", "--name", "client-a")
        self.assertFalse((self.root / "libraries" / "client-a").exists())
        self.cli("library-add", "--name", "client-a", "--execute")
        self.assertTrue((self.root / "libraries" / "client-a" / state.MARKER).is_file())
        for value in ("central", "client-a", "../outside", "con"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.cli("library-add", "--name", value, "--execute")

    def test_unregistered_project_cannot_enable_without_binding(self) -> None:
        central = self.initialize(False)
        write_skill(central / "writer")
        with self.assertRaisesRegex(SystemExit, "project-bind"):
            self.cli("link", "--source", str(central / "writer"), "--execute")
        self.assertFalse((self.project / ".agents").exists())

    def test_project_default_never_hides_catalog_or_relinks(self) -> None:
        central = self.initialize()
        write_skill(central / "writer")
        self.cli("library-add", "--name", "work", "--execute")
        self.cli("link", "--source", str(central / "writer"), "--link-type", self.link_type, "--execute")
        pointer = (self.home / state.CONFIG).read_bytes()
        self.cli("library-use", "--name", "work", "--execute")
        config = manager.load_effective_config(self.project, self.home)
        self.assertEqual(set(config["libraries"]), {"central", "work"})
        self.assertEqual(config["active_library"], "work")
        self.assertEqual(self.binding()["enabled"], {"writer": "central"})
        self.assertEqual(manager.immediate_link_target(self.project / ".agents" / "skills" / "writer"), central / "writer")
        self.assertEqual((self.home / state.CONFIG).read_bytes(), pointer)

    def test_missing_default_is_error_not_fallback(self) -> None:
        self.initialize()
        binding = self.binding()
        binding["default_library"] = "missing"
        self.json_write(self.project / state.CONFIG, binding)
        config = manager.load_effective_config(self.project, self.home)
        self.assertEqual(config["source"], "error")
        self.assertIn("不会自动换成 central", config["error"])

    def test_other_root_binding_is_error(self) -> None:
        self.initialize()
        binding = self.binding()
        binding["root_id"] = str(uuid.uuid4())
        self.json_write(self.project / state.CONFIG, binding)
        self.assertIn("另一个管理根", manager.load_effective_config(self.project, self.home)["error"])

    def test_copied_project_requires_explicit_new_identity(self) -> None:
        self.initialize()
        old_id = self.binding()["project_id"]
        original = self.project
        self.project = self.base / "copy"
        shutil.copytree(original, self.project)
        self.assertIn("project-rebind", manager.load_effective_config(self.project, self.home)["error"])
        with self.assertRaisesRegex(ValueError, "原项目路径仍存在"):
            self.cli("project-rebind", "--mode", "move", "--execute")
        self.cli("project-rebind", "--mode", "copy", "--execute")
        self.assertNotEqual(self.binding()["project_id"], old_id)
        self.assertEqual(len(self.catalog()["projects"]), 2)

    def test_moved_project_keeps_identity_after_explicit_rebind(self) -> None:
        self.initialize()
        old_id = self.binding()["project_id"]
        new = self.base / "moved"
        self.project.rename(new)
        self.project = new
        self.cli("project-rebind", "--mode", "move")
        self.assertEqual(manager.load_effective_config(self.project, self.home)["source"], "error")
        self.cli("project-rebind", "--mode", "move", "--execute")
        self.assertEqual(self.binding()["project_id"], old_id)
        self.assertEqual(self.catalog()["projects"][old_id]["path"], str(new))

    def test_same_basename_projects_have_distinct_identity(self) -> None:
        self.initialize(False)
        for parent in ("client-a", "client-b"):
            self.project = self.base / parent / "website"
            self.project.mkdir(parents=True)
            self.cli("project-bind", "--execute")
        self.assertEqual(len(self.catalog()["projects"]), 2)

    def test_project_list_checks_entries_and_reports_missing_projects(self) -> None:
        central = self.initialize()
        write_skill(central / "writer")
        self.cli("link", "--source", str(central / "writer"), "--link-type", self.link_type, "--execute")
        code, output = self.cli("project-list")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["projects"][0]["enabled"][0]["valid"])
        manager.remove_link_path(self.project / ".agents" / "skills" / "writer")
        code, output = self.cli("project-list")
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output)["projects"][0]["enabled"][0]["valid"])
        self.project.rename(self.base / "not-registered")
        code, output = self.cli("project-list")
        self.assertEqual(code, 1)
        self.assertEqual(len(self.catalog()["projects"]), 1)

    def test_link_and_unlink_update_enabled_records(self) -> None:
        central = self.initialize()
        write_skill(central / "writer")
        entry = self.project / ".agents" / "skills" / "writer"
        self.cli("link", "--source", str(central / "writer"), "--link-type", self.link_type, "--execute")
        self.assertEqual(self.binding()["enabled"], {"writer": "central"})
        self.cli("unlink", "--target", str(entry), "--execute")
        self.assertEqual(self.binding()["enabled"], {})
        self.assertTrue((central / "writer" / "SKILL.md").is_file())

    def test_binding_write_failure_rolls_back_created_link(self) -> None:
        central = self.initialize()
        write_skill(central / "writer")
        before = (self.project / state.CONFIG).read_bytes()
        with mock.patch.object(manager, "save_project_binding", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.cli("link", "--source", str(central / "writer"), "--link-type", self.link_type, "--execute")
        self.assertFalse(os.path.lexists(self.project / ".agents" / "skills" / "writer"))
        self.assertEqual((self.project / state.CONFIG).read_bytes(), before)

    def test_metadata_transaction_recovers_partial_write(self) -> None:
        self.initialize(False)
        original = (self.root / state.CATALOG).read_bytes()
        project_config = self.project / state.CONFIG
        real_write = state.atomic_bytes

        def fail_catalog(path: Path, content: bytes) -> None:
            if path == self.root / state.CATALOG:
                raise OSError("catalog unavailable")
            real_write(path, content)

        with mock.patch.object(state, "atomic_bytes", side_effect=fail_catalog):
            with self.assertRaisesRegex(OSError, "catalog unavailable"):
                self.cli("project-bind", "--execute")
        self.assertFalse(project_config.exists())
        self.assertEqual((self.root / state.CATALOG).read_bytes(), original)

    def test_metadata_stale_write_and_lock_are_rejected(self) -> None:
        self.initialize()
        path = self.project / state.CONFIG
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "预检后变化"):
            state.commit_metadata(self.root, {path: self.binding()}, {path: b"stale"})
        with state.root_lock(self.root):
            with self.assertRaises(FileExistsError):
                state.commit_metadata(self.root, {path: self.binding()}, {path: before})
        self.assertEqual(path.read_bytes(), before)

    def test_root_or_library_links_cannot_escape(self) -> None:
        self.initialize()
        outside = self.base / "outside"
        outside.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            manager.create_symlink(self.root / "libraries" / "escaped", outside, True, self.link_type)
        with self.assertRaisesRegex(ValueError, "包含链接"):
            self.cli("library-add", "--name", "escaped", "--execute")

    def make_v2(self) -> Path:
        old = self.base / "old-library"
        old.mkdir()
        write_skill(old / "writer")
        self.json_write(self.home / state.CONFIG, {"schema_version": 2,
                        "libraries": {"personal": {"path": str(old)}},
                        "active_library": "personal", "default_mode": "centralize"})
        return old

    def test_concurrent_binding_does_not_pair_old_catalog_with_new_snapshot(self) -> None:
        self.initialize(False)
        other = self.base / "other"
        other.mkdir()
        original_read = state.read_user
        injected = False

        def read_then_other_commit(home: Path):
            nonlocal injected
            result = original_read(home)
            if not injected:
                injected = True
                self.cli("project-bind", "--project", str(other), "--execute")
            return result

        with mock.patch.object(state, "read_user", side_effect=read_then_other_commit):
            with self.assertRaisesRegex(ValueError, "读取后变化"):
                self.cli("project-bind", "--execute")
        self.assertFalse((self.project / state.CONFIG).exists())
        catalog = state.read_catalog(self.root)
        self.assertEqual(len(catalog["projects"]), 1)
        self.assertIsNotNone(state.read_binding(other, catalog))

    def test_redirected_project_hub_cannot_write_outside_project(self) -> None:
        central = self.initialize()
        write_skill(central / "writer")
        foreign = self.home / ".agents" / "skills"
        foreign.mkdir(parents=True)
        hub = self.project / ".agents" / "skills"
        with contextlib.redirect_stdout(io.StringIO()):
            manager.create_symlink(hub, foreign, True, self.link_type)
        with self.assertRaisesRegex(ValueError, "包含链接"):
            self.cli("link", "--source", str(central / "writer"), "--link-type", self.link_type, "--execute")
        self.assertEqual(list(foreign.iterdir()), [])
        self.assertEqual(self.binding()["enabled"], {})
        code, output = self.cli("project-list")
        self.assertEqual(code, 1)
        self.assertIn("包含链接", json.loads(output)["projects"][0]["errors"][0]["error"])

    def test_v2_runtime_rejected_and_explicit_migration_preserves_original(self) -> None:
        old = self.make_v2()
        original = (old / "writer" / "SKILL.md").read_bytes()
        before = (self.home / state.CONFIG).read_bytes()
        self.assertEqual(manager.load_effective_config(self.project, self.home)["source"], "error")
        _, output = self.cli("migrate-config", "--root", str(self.root), "--main-library", "personal")
        plan = json.loads(output)
        self.assertFalse(self.root.exists())
        self.assertEqual((self.home / state.CONFIG).read_bytes(), before)
        self.cli("migrate-config", "--root", str(self.root), "--main-library", "personal",
                 "--expected-digest", plan["expected_digest"], "--execute")
        self.assertEqual((old / "writer" / "SKILL.md").read_bytes(), original)
        self.assertEqual((self.root / "libraries" / "central" / "writer" / "SKILL.md").read_bytes(), original)
        self.assertEqual(state.read_json(Path(plan["backup_config"])), json.loads(before))
        self.assertFalse((self.project / state.CONFIG).exists())
        self.assertEqual(set(self.catalog()["libraries"]), {"central"})

    def test_migration_requires_unchanged_plan_and_rejects_stale_receipts(self) -> None:
        old = self.make_v2()
        _, output = self.cli("migrate-config", "--root", str(self.root), "--main-library", "personal")
        digest = json.loads(output)["expected_digest"]
        (old / "writer" / "new.txt").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "expected-digest"):
            self.cli("migrate-config", "--root", str(self.root), "--main-library", "personal",
                     "--expected-digest", digest, "--execute")
        self.assertFalse(self.root.exists())
        (old / manager.LOCAL_RECORD_DIR).mkdir()
        with self.assertRaisesRegex(ValueError, "接管恢复凭据"):
            self.cli("migrate-config", "--root", str(self.root), "--main-library", "personal")

    def test_migration_copy_failure_keeps_old_pointer_and_contents(self) -> None:
        old = self.make_v2()
        before = (self.home / state.CONFIG).read_bytes()
        _, output = self.cli("migrate-config", "--root", str(self.root), "--main-library", "personal")
        digest = json.loads(output)["expected_digest"]
        with mock.patch.object(manager.shutil, "copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.cli("migrate-config", "--root", str(self.root), "--main-library", "personal",
                         "--expected-digest", digest, "--execute")
        self.assertEqual((self.home / state.CONFIG).read_bytes(), before)
        self.assertTrue((old / "writer" / "SKILL.md").is_file())

    def test_project_v2_replacement_is_explicit_and_keeps_backup(self) -> None:
        central = self.initialize(False)
        old = {"schema_version": 2, "libraries": {"personal": {"path": str(central)}},
               "active_library": "personal", "default_mode": "centralize"}
        self.json_write(self.project / state.CONFIG, old)
        with self.assertRaisesRegex(ValueError, "已存在"):
            self.cli("project-bind", "--execute")
        self.cli("project-bind", "--replace-v2", "--execute")
        self.assertEqual(state.read_json(self.project / ".skill-linker-v2-config.backup.json"), old)
        self.assertEqual(self.binding()["enabled"], {})

    def test_git_library_migration_rebuilds_entries_inside_new_root(self) -> None:
        central = self.initialize(False)
        source = self.base / "source"
        init_git_repo(source)
        write_skill(source / "skill", "writer")
        manager.run_git(source, ["add", "."], check=True)
        manager.run_git(source, ["commit", "-m", "skill"], check=True)
        self.cli("install-repo", "--repo-url", str(source), "--skills", "writer=skill",
                 "--link-type", self.link_type, "--execute")
        old_head = next(iter(manager.read_registry(central)["repositories"].values()))["revision"]
        self.json_write(self.home / state.CONFIG, {"schema_version": 2,
                        "libraries": {"personal": {"path": str(central)}},
                        "active_library": "personal", "default_mode": "centralize"})
        destination = self.base / "new-root"
        _, output = self.cli("migrate-config", "--root", str(destination), "--main-library", "personal")
        self.cli("migrate-config", "--root", str(destination), "--main-library", "personal",
                 "--expected-digest", json.loads(output)["expected_digest"], "--link-type", self.link_type, "--execute")
        new_central = destination / "libraries" / "central"
        record = next(iter(manager.read_registry(new_central)["repositories"].values()))
        self.assertEqual(record["revision"], old_head)
        self.assertEqual(manager.immediate_link_target(new_central / "writer"), new_central / record["path"] / "skill")
        self.assertTrue((central / "writer" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
