"""First-use inventory and recoverable adoption in isolated local fixtures."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from test_skill_manager import skill_manager as manager, write_config, write_skill, init_git_repo


class OnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.project = self.root / "含空格 项目"
        self.central = self.home / ".e8-skill-linker" / "libraries" / "central"
        for path in (self.home, self.project, self.central):
            path.mkdir(parents=True, exist_ok=True)
        self.link_type = "junction" if os.name == "nt" else "symlink"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch.object(sys, "argv", ["skill_manager.py", *arguments]), contextlib.redirect_stdout(output):
            code = manager.main()
        return code, output.getvalue()

    def source(self, scope: str = "project", name: str = "demo") -> Path:
        base = self.home if scope == "user" else self.project
        path = base / ".agents" / "skills" / name
        write_skill(path)
        (path / "空目录").mkdir()
        (path / "script.txt").write_text("中文内容\n", encoding="utf-8")
        return path

    def configure(self) -> None:
        write_config(self.home / ".skill-linker.json", self.central, self.project)

    def migration_args(self, source: Path) -> list[str]:
        return ["migrate", "--project", str(self.project), "--home", str(self.home),
                "--source", str(source), "--central", str(self.central), "--link-type", self.link_type]

    def adopt(self, source: Path) -> dict:
        _, output = self.cli(*self.migration_args(source))
        plan, _ = json.JSONDecoder().raw_decode(output)
        self.cli(*self.migration_args(source), "--expected-digest", plan["expected_digest"],
                 "--dependencies-reviewed", "--execute")
        return plan

    def restore_args(self, plan: dict) -> list[str]:
        return ["restore-adoption", "--project", str(self.project), "--home", str(self.home),
                "--receipt", plan["receipt"], "--link-type", self.link_type]

    def test_unconfigured_inventory_is_read_only_and_explains_skills(self) -> None:
        source = self.source()
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertTrue(report["read_only"])
        self.assertEqual(report["manager"]["recommendation"], "offer-user-install-after-scan")
        self.assertEqual(report["skills"][0]["description"], "test")
        self.assertEqual(report["skills"][0]["source"]["status"], "unknown")
        self.assertFalse(report["defaults"]["migrate_existing"])
        self.assertFalse((self.home / ".skill-linker.json").exists())
        self.assertFalse((self.project / ".skill-linker-backups").exists())
        self.assertEqual(manager.read_skill_name(source), "demo")

    def test_block_description_and_missing_description(self) -> None:
        source = self.source()
        (source / "SKILL.md").write_text("---\nname: demo\ndescription: >-\n  写文章，\n  并检查格式。\n---\n", encoding="utf-8")
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertEqual(report["skills"][0]["description"], "写文章， 并检查格式。")
        (source / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
        row = manager.onboarding_inventory(self.project, self.home)["skills"][0]
        self.assertIsNone(row["description"])
        self.assertTrue(row["issues"])

    def test_parent_business_git_remote_is_not_skill_source(self) -> None:
        project = self.root / "business-repo"
        init_git_repo(project)
        manager.run_git(project, ["remote", "add", "origin", "https://github.com/company/business.git"], check=True)
        self.project = project
        source = self.source()
        evidence = manager.source_evidence(source, self.project, self.home)
        self.assertEqual(evidence["status"], "unknown")
        self.assertEqual(evidence["evidence"][0]["kind"], "enclosing-project-not-source")
        self.assertNotIn("url", evidence["evidence"][0])

    def test_document_urls_are_candidates_not_verified_origins(self) -> None:
        source = self.source()
        (source / "README.md").write_text("感谢 https://github.com/owner/tool，也依赖 https://github.com/other/dependency", encoding="utf-8")
        report = manager.source_evidence(source, self.project, self.home)
        self.assertEqual(report["status"], "unverified-evidence")
        self.assertFalse(report["automatic_updates"])
        self.assertTrue(all(item["kind"] == "document-url-candidate" for item in report["evidence"]))

    def test_direct_git_origin_is_recorded_without_exposing_credentials(self) -> None:
        source = self.project / ".agents" / "skills" / "git-demo"
        source.parent.mkdir(parents=True)
        init_git_repo(source)
        (source / "SKILL.md").write_text("---\nname: git-demo\ndescription: Git fixture\n---\n", encoding="utf-8")
        manager.run_git(source, ["remote", "add", "origin", "https://user:secret@github.com/owner/tool.git?token=secret"], check=True)
        evidence = manager.source_evidence(source, self.project, self.home)
        self.assertEqual(evidence["evidence"][0]["kind"], "git-checkout")
        self.assertNotIn("secret", json.dumps(evidence))
        self.assertFalse(evidence["automatic_updates"])

    def test_identical_and_different_copies_are_not_conflated(self) -> None:
        self.source("project")
        user = self.source("user")
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertEqual(report["same_name_groups"][0]["relation"], "identical-copies")
        (user / "script.txt").write_text("不同内容", encoding="utf-8")
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertEqual(report["same_name_groups"][0]["relation"], "different-content")

    def test_multiple_entries_to_one_original_are_not_duplicate_copies(self) -> None:
        source = self.source()
        entry = self.home / ".agents" / "skills" / "demo"
        with contextlib.redirect_stdout(io.StringIO()):
            manager.create_symlink(entry, source, True, self.link_type)
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertEqual(report["same_name_groups"][0]["relation"], "same-original")
        self.assertEqual(report["summary"]["unique_originals"], 1)

    def test_invalid_config_does_not_hide_inventory(self) -> None:
        self.source()
        (self.home / ".skill-linker.json").write_text("{bad", encoding="utf-8")
        code, output = self.cli("onboard", "--project", str(self.project), "--home", str(self.home))
        report = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(report["next_step"], "review-config-error")
        self.assertEqual(len(report["skills"]), 1)

    def test_broken_registry_is_reported_not_adopted_as_empty(self) -> None:
        self.configure()
        (self.central / ".repos" / "unregistered").mkdir(parents=True)
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertEqual(report["central_libraries"][0]["status"], "invalid")
        self.assertTrue(report["errors"])

    def test_external_manager_entry_is_not_recommended_for_adoption(self) -> None:
        actual = self.home / ".codex" / "plugins" / "fixture" / "demo"
        write_skill(actual)
        entry = self.home / ".agents" / "skills" / "demo"
        with contextlib.redirect_stdout(io.StringIO()):
            manager.create_symlink(entry, actual, True, self.link_type)
        row = manager.onboarding_inventory(self.project, self.home)["skills"][0]
        self.assertEqual(row["management"], "external-manager")
        self.assertEqual(row["recommendation"], "keep")

    def test_installer_lock_is_a_format_review_not_guessed_source(self) -> None:
        (self.project / "skills-lock.json").write_text('{"unexpected": "format"}', encoding="utf-8")
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertEqual(report["installer_records"][0]["status"], "format-not-interpreted-review-required")

    def test_migration_dry_run_creates_no_backup_or_central_content(self) -> None:
        self.configure()
        source = self.source()
        _, output = self.cli(*self.migration_args(source))
        plan, _ = json.JSONDecoder().raw_decode(output)
        self.assertEqual(plan["preserved_scope"], "project")
        self.assertFalse(Path(plan["receipt"]).exists())
        self.assertEqual([p for p in self.central.iterdir() if p.name != manager.root_state.MARKER], [])
        self.assertFalse(source.is_symlink() or manager.is_junction(source))

    def test_content_change_after_plan_is_rejected_before_writes(self) -> None:
        self.configure()
        source = self.source()
        _, output = self.cli(*self.migration_args(source))
        plan, _ = json.JSONDecoder().raw_decode(output)
        (source / "script.txt").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "expected-digest"):
            self.cli(*self.migration_args(source), "--expected-digest", plan["expected_digest"], "--dependencies-reviewed", "--execute")
        self.assertEqual([p for p in self.central.iterdir() if p.name != manager.root_state.MARKER], [])

    def test_execute_requires_digest_and_dependency_review(self) -> None:
        self.configure()
        source = self.source()
        digest = manager.manifest_digest(manager.plain_tree_manifest(source))
        for flags in ([], ["--expected-digest", digest], ["--dependencies-reviewed"]):
            with self.subTest(flags=flags), self.assertRaisesRegex(SystemExit, "expected-digest"):
                self.cli(*self.migration_args(source), *flags, "--execute")
        self.assertEqual([p for p in self.central.iterdir() if p.name != manager.root_state.MARKER], [])
        self.assertFalse((self.project / ".skill-linker-backups").exists())

    def test_initialization_then_selected_adoption_leaves_other_skills_untouched(self) -> None:
        """CLI lifecycle evidence, not proof of a conversational approval boundary."""
        user_source = self.source("user")
        project_source = self.source("project")
        (project_source / "script.txt").write_text("项目定制内容", encoding="utf-8")
        project_before = manager.plain_tree_manifest(project_source)
        user_before = manager.plain_tree_manifest(user_source)
        report = manager.onboarding_inventory(self.project, self.home)
        self.assertEqual(report["central_libraries"], [])
        self.assertEqual(report["same_name_groups"][0]["relation"], "different-content")

        self.central = self.home / "new-management" / "libraries" / "central"
        config_args = ["root-init", "--project", str(self.project), "--home", str(self.home),
                       "--root", str(self.central.parent.parent)]
        self.cli(*config_args)
        self.assertFalse(self.central.exists())
        self.assertFalse((self.home / ".skill-linker.json").exists())
        self.cli(*config_args, "--execute")
        self.assertEqual(manager.plain_tree_manifest(user_source), user_before)
        self.assertEqual(manager.plain_tree_manifest(project_source), project_before)
        self.assertEqual([p for p in self.central.iterdir() if p.name != manager.root_state.MARKER], [])

        plan = self.adopt(user_source)
        self.assertEqual(plan["preserved_scope"], "user")
        self.assertEqual(manager.immediate_link_target(user_source), self.central / "demo")
        self.assertFalse(project_source.is_symlink() or manager.is_junction(project_source))
        self.assertEqual(manager.plain_tree_manifest(project_source), project_before)
        self.cli(*self.restore_args(plan), "--execute")
        self.assertEqual(manager.plain_tree_manifest(user_source), user_before)
        self.assertEqual(manager.plain_tree_manifest(project_source), project_before)

    def test_adopted_alias_uses_identity_record_and_detects_content_drift(self) -> None:
        self.configure()
        source = self.source()
        alias = source.with_name("old-folder-name")
        source.rename(alias)
        self.adopt(alias)
        row = next(row for row in manager.onboarding_inventory(self.project, self.home)["skills"]
                   if row["path"] == str(alias))
        self.assertEqual(row["management"], "skill-linker-local")
        self.assertEqual(row["name"], "demo")
        (alias / "script.txt").write_text("接管后修改", encoding="utf-8")
        row = next(row for row in manager.onboarding_inventory(self.project, self.home)["skills"]
                   if row["path"] == str(alias))
        self.assertTrue(any("内容已变化" in issue for issue in row["issues"]))

    def test_restore_rejects_modified_backup_without_removing_entry(self) -> None:
        self.configure()
        source = self.source()
        plan = self.adopt(source)
        (Path(plan["backup_original"]) / "script.txt").write_text("变动的备份", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "备份内容已改变"):
            self.cli(*self.restore_args(plan), "--execute")
        self.assertEqual(manager.immediate_link_target(source), self.central / "demo")

    def test_adoption_preserves_user_scope_backup_and_all_files(self) -> None:
        self.configure()
        source = self.source("user")
        before = manager.plain_tree_manifest(source)
        plan = self.adopt(source)
        self.assertEqual(manager.immediate_link_target(source), self.central / "demo")
        self.assertEqual(manager.plain_tree_manifest(Path(plan["backup_original"])), before)
        self.assertEqual(manager.plain_tree_manifest(source), before)
        self.assertFalse((self.project / ".agents").exists())
        self.assertTrue((source / "空目录").is_dir())
        row = manager.onboarding_inventory(self.project, self.home)["skills"][0]
        self.assertEqual(row["management"], "skill-linker-local")
        self.assertFalse(row["source"]["automatic_updates"])

    def test_link_failure_restores_source_and_preserves_failed_copy(self) -> None:
        self.configure()
        source = self.source()
        before = manager.plain_tree_manifest(source)
        with mock.patch.object(manager, "create_symlink", side_effect=OSError("link failed")):
            with self.assertRaisesRegex(OSError, "link failed"):
                self.adopt(source)
        self.assertEqual(manager.plain_tree_manifest(source), before)
        self.assertFalse((self.central / "demo").exists())
        failures = list(self.central.glob(".skill-linker-failed-*"))
        self.assertEqual(len(failures), 1)

    def test_cross_volume_rollback_never_renames_copy_into_backup_volume(self) -> None:
        self.configure()
        source = self.source()
        real_rename = Path.rename

        def simulated_volumes(path: Path, destination: Path) -> Path:
            if manager.is_path_inside(path, self.central) != manager.is_path_inside(destination, self.central):
                raise OSError(18, "cross-device rename")
            return real_rename(path, destination)

        with mock.patch.object(Path, "rename", simulated_volumes), mock.patch.object(
                manager, "create_symlink", side_effect=OSError("link failed")):
            with self.assertRaisesRegex(OSError, "link failed"):
                self.adopt(source)
        self.assertTrue((source / "SKILL.md").is_file())
        self.assertFalse((self.central / "demo").exists())
        receipt = next((self.project / ".skill-linker-backups").rglob("receipt.json"))
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["status"], "failed-original-preserved")

    def test_global_root_is_rejected_before_scope_can_expand(self) -> None:
        global_root = self.home / ".codex" / "skills" / "managed"
        with self.assertRaisesRegex(ValueError, "Agent 发现目录"):
            self.cli("root-init", "--project", str(self.project), "--home", str(self.home),
                     "--root", str(global_root), "--execute")
        self.assertFalse(global_root.exists())

    def test_bom_skill_is_consistent_across_inventory_adoption_and_restore(self) -> None:
        self.configure()
        source = self.source()
        (source / "SKILL.md").write_text("---\nname: demo\ndescription: test\n---\n", encoding="utf-8-sig")
        original_bytes = (source / "SKILL.md").read_bytes()
        self.assertEqual(manager.onboarding_inventory(self.project, self.home)["skills"][0]["name"], "demo")
        plan = self.adopt(source)
        self.cli(*self.restore_args(plan), "--execute")
        self.assertEqual((source / "SKILL.md").read_bytes(), original_bytes)

    def test_copy_failure_never_moves_original(self) -> None:
        self.configure()
        source = self.source()
        with mock.patch.object(manager.shutil, "copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.adopt(source)
        self.assertTrue((source / "SKILL.md").is_file())
        self.assertFalse(source.is_symlink() or manager.is_junction(source))
        self.assertFalse((self.central / "demo").exists())

    def test_restore_preserves_central_copy_and_restores_real_directory(self) -> None:
        self.configure()
        source = self.source()
        before = manager.plain_tree_manifest(source)
        plan = self.adopt(source)
        self.cli(*self.restore_args(plan))
        self.assertTrue(source.is_symlink() or manager.is_junction(source))
        self.cli(*self.restore_args(plan), "--execute")
        self.assertFalse(source.is_symlink() or manager.is_junction(source))
        self.assertEqual(manager.plain_tree_manifest(source), before)
        self.assertEqual(manager.plain_tree_manifest(self.central / "demo"), before)

    def test_restore_metadata_read_failure_keeps_adoption_intact(self) -> None:
        self.configure()
        source = self.source(scope="user")
        plan = self.adopt(source)
        receipt = Path(plan["receipt"])
        before = receipt.read_bytes()
        real_read_user = manager.root_state.read_user
        calls = 0

        def fail_restore_read(home: Path):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("root metadata unavailable")
            return real_read_user(home)

        with mock.patch.object(manager.root_state, "read_user", side_effect=fail_restore_read):
            with self.assertRaisesRegex(OSError, "root metadata unavailable"):
                self.cli(*self.restore_args(plan), "--execute")
        self.assertTrue(source.is_symlink() or manager.is_junction(source))
        self.assertEqual(manager.immediate_link_target(source), self.central / "demo")
        self.assertTrue((receipt.parent / "original" / "SKILL.md").is_file())
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual((self.central / manager.LOCAL_RECORD_DIR / "demo.json").read_bytes(), before)

    def test_restore_refuses_changed_central_content(self) -> None:
        self.configure()
        source = self.source()
        plan = self.adopt(source)
        (source / "script.txt").write_text("用户修改", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "中央副本已改变"):
            self.cli(*self.restore_args(plan), "--execute")
        self.assertEqual((source / "script.txt").read_text(encoding="utf-8"), "用户修改")

    def test_nested_links_and_git_metadata_are_not_snapshot_copied(self) -> None:
        self.configure()
        source = self.source()
        outside = self.root / "outside"
        outside.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            manager.create_symlink(source / "external", outside, True, self.link_type)
        with self.assertRaisesRegex(ValueError, "包含链接"):
            self.cli(*self.migration_args(source))
        manager.remove_link_path(source / "external")
        (source / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "Git 元数据"):
            self.cli(*self.migration_args(source))

    def test_existing_destination_and_forged_receipt_do_not_overwrite(self) -> None:
        self.configure()
        source = self.source()
        plan = self.adopt(source)
        receipt = Path(plan["receipt"])
        record = json.loads(receipt.read_text(encoding="utf-8"))
        record["source"] = str(self.root / "outside")
        receipt.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.cli(*self.restore_args(plan), "--execute")
        self.assertTrue(source.is_symlink() or manager.is_junction(source))


if __name__ == "__main__":
    unittest.main()
