"""End-to-end library workflows using temporary Git repositories, never GitHub."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_skill_manager import bind_project, init_git_repo, skill_manager, write_config, write_skill


class RepositoryWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.central = self.home / ".e8-skill-linker" / "libraries" / "central"
        self.central.mkdir(parents=True)
        self.project.mkdir()
        write_config(self.home / ".skill-linker.json", self.central, self.project)
        self.source = self.root / "source-pack"
        init_git_repo(self.source)
        write_skill(self.source / "skills" / "demo")
        write_skill(self.source / "skills" / "reviewer")
        self.commit("initial skills")
        self.link_type = "junction" if os.name == "nt" else "symlink"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, repo: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True,
            text=True, encoding="utf-8",
        ).stdout.strip()

    def commit(self, message: str) -> None:
        self.git(self.source, "add", "-A")
        self.git(self.source, "commit", "-m", message)

    def cli(self, command: str, *args: str) -> tuple[int, str]:
        argv = ["skill_manager.py", command, "--home", str(self.home), "--project", str(self.project), *args]
        output = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            result = skill_manager.main()
        return result, output.getvalue()

    def install(self, specs: str = "demo=skills/demo", library: str = "central") -> Path:
        self.cli("install-repo", "--repo-url", str(self.source), "--skills", specs,
                 "--library", library, "--link-type", self.link_type, "--execute")
        central = skill_manager.configured_central(self.project, self.home, library)
        record = next(iter(skill_manager.read_registry(central)["repositories"].values()))
        return central / record["path"]

    def add_work(self) -> Path:
        self.cli("library-add", "--name", "work", "--execute")
        return self.central.parent / "work"

    def test_project_link_preserves_central_entry_after_retarget(self) -> None:
        self.project = self.root / "含空格 项目"
        self.project.mkdir()
        bind_project(self.home, self.project)
        repo = self.install()
        self.cli("link", "--source", str(repo / "skills" / "demo"), "--link-type", self.link_type, "--execute")
        project_entry = self.project / ".agents" / "skills" / "demo"
        central_entry = self.central / "demo"
        self.assertEqual(skill_manager.immediate_link_target(project_entry), central_entry)
        replacement = self.root / "replacement" / "demo"
        write_skill(replacement)
        (replacement / "version.txt").write_text("new", encoding="utf-8")
        skill_manager.remove_link_path(central_entry)
        with contextlib.redirect_stdout(io.StringIO()):
            skill_manager.create_symlink(central_entry, replacement, True, self.link_type)
        self.assertEqual((project_entry / "version.txt").read_text(encoding="utf-8"), "new")

    def test_existing_direct_link_is_not_mistaken_for_central_entry_link(self) -> None:
        repo = self.install()
        entry = self.project / ".agents" / "skills" / "demo"
        with contextlib.redirect_stdout(io.StringIO()):
            skill_manager.create_symlink(entry, repo / "skills" / "demo", True, self.link_type)
        with self.assertRaisesRegex(SystemExit, "已有其他链接"):
            self.cli("link", "--source", str(self.central / "demo"), "--execute")

    def test_reuse_adds_skill_and_enables_existing_skill_without_recloning(self) -> None:
        repo = self.install()
        head = self.git(repo, "rev-parse", "HEAD")
        self.cli("install-repo", "--repo-url", str(self.source),
                 "--skills", "demo=skills/demo,reviewer=skills/reviewer", "--enable-project",
                 "--link-type", self.link_type, "--execute")
        record = next(iter(skill_manager.read_registry(self.central)["repositories"].values()))
        self.assertEqual(set(record["skills"]), {"demo", "reviewer"})
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head)
        self.assertEqual(skill_manager.immediate_link_target(self.project / ".agents" / "skills" / "demo"), self.central / "demo")
        self.assertTrue((self.project / ".agents" / "skills" / "reviewer" / "SKILL.md").is_file())
        self.install("demo=skills/demo,reviewer=skills/reviewer")

    def test_reuse_rolls_back_only_new_entries(self) -> None:
        repo = self.install()
        registry_before = skill_manager.registry_path(self.central).read_bytes()
        with mock.patch.object(skill_manager, "write_registry", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(OSError, "write failed"):
                self.install("demo=skills/demo,reviewer=skills/reviewer")
        self.assertTrue((repo / ".git").is_dir())
        self.assertTrue((self.central / "demo" / "SKILL.md").is_file())
        self.assertFalse(os.path.lexists(self.central / "reviewer"))
        self.assertEqual(skill_manager.registry_path(self.central).read_bytes(), registry_before)

    def test_binding_write_failure_restores_registry_and_existing_repository(self) -> None:
        repo = self.install()
        registry_before = skill_manager.registry_path(self.central).read_bytes()
        binding_path = self.project / ".skill-linker.json"
        binding_before = binding_path.read_bytes()
        with mock.patch.object(skill_manager, "save_project_binding", side_effect=OSError("binding write failed")):
            with self.assertRaisesRegex(OSError, "binding write failed"):
                self.cli("install-repo", "--repo-url", str(self.source),
                         "--skills", "demo=skills/demo,reviewer=skills/reviewer", "--enable-project",
                         "--link-type", self.link_type, "--execute")
        self.assertEqual(skill_manager.registry_path(self.central).read_bytes(), registry_before)
        self.assertEqual(binding_path.read_bytes(), binding_before)
        self.assertTrue((repo / ".git").is_dir())
        self.assertTrue((self.central / "demo" / "SKILL.md").is_file())
        self.assertFalse(os.path.lexists(self.central / "reviewer"))
        for name in ("demo", "reviewer"):
            self.assertFalse(os.path.lexists(self.project / ".agents" / "skills" / name))

    def test_update_impact_lists_registered_project_origins(self) -> None:
        self.install()
        self.cli("link", "--source", str(self.central / "demo"), "--link-type", self.link_type, "--execute")
        _, output = self.cli("updates")
        impact = json.loads(output)["repositories"][0]["registered_project_impact"]
        self.assertEqual(impact["scope"], "registered-projects-only")
        self.assertEqual(impact["inspection_errors"], [])
        self.assertEqual(impact["affected"], [{"project": str(self.project), "declared_skills": ["demo"], "unrecorded_links": []}])
        self.cli("unlink", "--target", str(self.project / ".agents" / "skills" / "demo"), "--execute")
        _, output = self.cli("updates")
        self.assertEqual(json.loads(output)["repositories"][0]["registered_project_impact"]["affected"], [])

    def test_root_skill_name_may_differ_from_repository_name(self) -> None:
        (self.source / "SKILL.md").write_text("---\nname: root-writer\ndescription: test\n---\n", encoding="utf-8")
        self.commit("root skill")
        self.install("root-writer=.")
        self.assertTrue((self.central / "root-writer" / "SKILL.md").is_file())

    def test_arbitrary_source_directory_names_support_install_link_and_update(self) -> None:
        write_skill(self.source / "skill", "codex-with-chatgpt")
        write_skill(self.source / "packages" / "bridge" / "definition", "nested-integration")
        self.commit("skills in generic source directories")
        specs = "codex-with-chatgpt=skill,nested-integration=packages/bridge/definition"
        repo = self.install(specs)
        self.cli("install-repo", "--repo-url", str(self.source), "--skills", specs,
                 "--enable-project", "--link-type", self.link_type, "--execute")
        record = next(iter(skill_manager.read_registry(self.central)["repositories"].values()))
        for name, subpath in (("codex-with-chatgpt", "skill"), ("nested-integration", "packages/bridge/definition")):
            with self.subTest(name=name):
                self.assertEqual(record["skills"][name]["subpath"], subpath)
                entry = self.project / ".agents" / "skills" / name
                self.assertEqual(skill_manager.immediate_link_target(entry), self.central / name)
                self.assertEqual(skill_manager.immediate_link_target(self.central / name), repo / subpath)
                self.assertEqual(skill_manager.read_skill_name(entry), name)
        self.assertFalse((repo / "codex-with-chatgpt").exists())
        (self.source / "skill" / "guide.txt").write_text("updated", encoding="utf-8")
        self.commit("update generic skill directory")
        _, output = self.cli("updates", "--execute")
        self.assertEqual(json.loads(output)["repositories"][0]["impact"]["directly_changed_skills"], ["codex-with-chatgpt"])
        self.cli("update", "--repo", str(repo), "--execute")
        self.assertEqual((self.project / ".agents" / "skills" / "codex-with-chatgpt" / "guide.txt").read_text(encoding="utf-8"), "updated")
        code, output = self.cli("check", "--include-central")
        self.assertEqual(code, 0, output)

    def test_generic_directory_still_requires_matching_frontmatter_identity(self) -> None:
        write_skill(self.source / "skill", "actual-name")
        self.commit("generic skill source")
        with self.assertRaisesRegex(SystemExit, "skill name 与安装计划不一致"):
            self.install("requested-name=skill")
        self.assertFalse(os.path.lexists(self.central / "requested-name"))
        self.assertFalse(skill_manager.registry_path(self.central).exists())
        self.assertEqual(list((self.central / ".repos").rglob(".git")), [])

    def test_explicit_skill_mapping_rejects_path_escape(self) -> None:
        for subpath in ("../skill", "packages/../../skill", str(self.root / "outside")):
            with self.subTest(subpath=subpath), self.assertRaisesRegex(SystemExit, "安全相对路径"):
                skill_manager.parse_skill_specs(f"codex-with-chatgpt={subpath}")

    def test_fetch_detects_real_upstream_changes_and_reports_new_skills(self) -> None:
        repo = self.install()
        (self.source / "skills" / "demo" / "guide.txt").write_text("新版本", encoding="utf-8")
        write_skill(self.source / "skills" / "new-skill")
        self.commit("skill update")
        _, local = self.cli("updates")
        local_report = json.loads(local)["repositories"][0]
        self.assertEqual(local_report["freshness"], "local-cache")
        self.assertEqual(local_report["behind"], 0)
        code, remote = self.cli("updates", "--execute")
        report = json.loads(remote)["repositories"][0]
        self.assertEqual(code, 0)
        self.assertEqual(report["freshness"], "fetched")
        self.assertEqual(report["behind"], 1)
        self.assertEqual(report["impact"]["directly_changed_skills"], ["demo"])
        self.assertIn("skills/new-skill/SKILL.md", report["impact"]["added_skill_files"])
        self.cli("update", "--repo", str(repo), "--library", "central", "--execute")
        record = next(iter(skill_manager.read_registry(self.central)["repositories"].values()))
        self.assertEqual(record["revision"], self.git(repo, "rev-parse", "HEAD"))
        self.assertEqual((self.central / "demo" / "guide.txt").read_text(encoding="utf-8"), "新版本")
        self.assertFalse((self.central / "new-skill").exists())

    def test_failed_fetch_reports_unknown_without_stale_counts(self) -> None:
        repo = self.install()
        unavailable = str(self.root / "missing-remote")
        self.git(repo, "remote", "set-url", "origin", unavailable)
        registry = skill_manager.read_registry(self.central)
        next(iter(registry["repositories"].values()))["url"] = unavailable
        skill_manager.write_registry(self.central, registry)
        code, output = self.cli("updates", "--execute")
        report = json.loads(output)["repositories"][0]
        self.assertEqual(code, 1)
        self.assertEqual(report["freshness"], "fetch-failed")
        self.assertEqual(report["update_state"], "unknown")
        self.assertNotIn("behind", report)

    def test_upstream_move_is_blocked_before_worktree_or_registry_changes(self) -> None:
        repo = self.install()
        head = self.git(repo, "rev-parse", "HEAD")
        manifest = skill_manager.registry_path(self.central).read_bytes()
        self.git(self.source, "mv", "skills/demo", "skills/moved")
        self.commit("move installed skill")
        with self.assertRaisesRegex(SystemExit, "候选版本破坏"):
            self.cli("update", "--repo", str(repo), "--execute")
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head)
        self.assertEqual(skill_manager.registry_path(self.central).read_bytes(), manifest)
        self.assertTrue((self.central / "demo" / "SKILL.md").is_file())

    def test_upstream_name_change_is_blocked(self) -> None:
        repo = self.install()
        head = self.git(repo, "rev-parse", "HEAD")
        (self.source / "skills" / "demo" / "SKILL.md").write_text("---\nname: changed\ndescription: test\n---\n", encoding="utf-8")
        self.commit("rename identity")
        with self.assertRaisesRegex(SystemExit, "候选版本破坏"):
            self.cli("update", "--repo", str(repo), "--execute")
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head)

    def test_library_selection_isolates_repositories_and_keeps_default(self) -> None:
        work = self.add_work()
        personal_repo = self.install()
        original = self.git(personal_repo, "rev-parse", "HEAD")
        work_repo = self.install(library="work")
        config_before = (self.home / ".skill-linker.json").read_bytes()
        (self.source / "skills" / "demo" / "work.txt").write_text("update", encoding="utf-8")
        self.commit("new version")
        self.cli("update", "--repo", str(work_repo), "--library", "work", "--execute")
        self.assertEqual(self.git(personal_repo, "rev-parse", "HEAD"), original)
        self.assertTrue((work / "demo" / "work.txt").is_file())
        self.assertFalse((self.central / "demo" / "work.txt").exists())
        self.assertEqual((self.home / ".skill-linker.json").read_bytes(), config_before)
        with self.assertRaisesRegex(SystemExit, "不属于指定中央库"):
            self.cli("update", "--repo", str(personal_repo), "--library", "work", "--execute")
        code, output = self.cli("updates", "--all-libraries", "--execute")
        self.assertEqual(code, 0)
        self.assertEqual({row["library"] for row in json.loads(output)["repositories"]}, {"central", "work"})
        code, output = self.cli("check", "--all-libraries")
        self.assertEqual(code, 0, output)

    def test_project_binding_keeps_user_library_catalog_visible(self) -> None:
        self.add_work()
        code, output = self.cli("updates", "--library", "work")
        self.assertEqual(code, 0)
        self.assertEqual(set(skill_manager.load_effective_config(self.project, self.home)["libraries"]), {"central", "work"})

    def test_switch_reports_existing_project_ownership_without_relinking(self) -> None:
        self.add_work()
        self.install()
        self.cli("link", "--source", str(self.central / "demo"), "--link-type", self.link_type, "--execute")
        _, output = self.cli("library-use", "--name", "work", "--execute")
        plan, _ = json.JSONDecoder().raw_decode(output)
        self.assertEqual(plan["enabled_unchanged"], {"demo": "central"})
        self.assertEqual(skill_manager.immediate_link_target(self.project / ".agents" / "skills" / "demo"), self.central / "demo")

    def test_check_fails_when_registered_skill_or_commit_is_missing(self) -> None:
        repo = self.install()
        (repo / "skills" / "demo" / "SKILL.md").unlink()
        code, output = self.cli("check", "--library", "central")
        self.assertEqual(code, 1)
        self.assertTrue(json.loads(output)["problems"])

    def test_dirty_repository_is_not_updated(self) -> None:
        repo = self.install()
        (repo / "untracked.txt").write_text("local", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "本地改动"):
            self.cli("update", "--repo", str(repo), "--execute")

    def test_divergence_is_reported_and_update_leaves_local_commit(self) -> None:
        repo = self.install()
        self.git(repo, "config", "user.name", "Local Tester")
        self.git(repo, "config", "user.email", "local@example.com")
        (repo / "local.txt").write_text("local", encoding="utf-8")
        self.git(repo, "add", "local.txt")
        self.git(repo, "commit", "-m", "local commit")
        skill_manager.sync_registry_revision(repo)
        head = self.git(repo, "rev-parse", "HEAD")
        (self.source / "remote.txt").write_text("remote", encoding="utf-8")
        self.commit("remote commit")
        _, output = self.cli("updates", "--execute")
        self.assertEqual(json.loads(output)["repositories"][0]["update_state"], "diverged")
        with self.assertRaisesRegex(SystemExit, "分叉"):
            self.cli("update", "--repo", str(repo), "--execute")
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head)

    def test_no_upstream_is_unknown_even_after_successful_fetch(self) -> None:
        repo = self.install()
        self.git(repo, "branch", "--unset-upstream")
        _, output = self.cli("updates", "--execute")
        report = json.loads(output)["repositories"][0]
        self.assertEqual(report["freshness"], "fetched")
        self.assertEqual(report["update_state"], "unknown")
        self.assertIsNone(report["behind"])
        with self.assertRaisesRegex(SystemExit, "没有 upstream"):
            self.cli("update", "--repo", str(repo), "--execute")

    def test_dry_run_install_creates_neither_entries_nor_registry(self) -> None:
        self.cli("install-repo", "--repo-url", str(self.source), "--skills", "demo=skills/demo", "--enable-project")
        self.assertFalse((self.central / ".repos").exists())
        self.assertFalse(skill_manager.registry_path(self.central).exists())
        self.assertFalse((self.project / ".agents").exists())

    def test_project_enablement_dry_run_preserves_existing_installation(self) -> None:
        repo = self.install()
        registry = skill_manager.registry_path(self.central)
        before = (registry.read_bytes(), registry.stat().st_mtime_ns)
        head = self.git(repo, "rev-parse", "HEAD")
        _, output = self.cli("install-repo", "--repo-url", str(self.source),
                             "--skills", "demo=skills/demo", "--enable-project")
        plan, _ = json.JSONDecoder().raw_decode(output)
        self.assertTrue(plan["planned_repo_install"]["reuse_repository"])
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual((registry.read_bytes(), registry.stat().st_mtime_ns), before)
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head)

    def test_already_installed_inspection_does_not_rewrite_registry_or_links(self) -> None:
        repo = self.install()
        self.cli("link", "--source", str(self.central / "demo"),
                 "--link-type", self.link_type, "--execute")
        registry = skill_manager.registry_path(self.central)
        entry = self.project / ".agents" / "skills" / "demo"
        before = (registry.read_bytes(), registry.stat().st_mtime_ns, entry.lstat().st_mtime_ns)
        # Read-only checks are the evidence for the no-change conversational branch.
        code, output = self.cli("check", "--include-central")
        self.assertEqual(code, 0, output)
        report = json.loads(output)
        self.assertEqual(report["problems"], [])
        self.assertEqual(Path(report["project_links"][0]["path"]), entry)
        self.assertEqual((registry.read_bytes(), registry.stat().st_mtime_ns, entry.lstat().st_mtime_ns), before)
        self.assertEqual(skill_manager.immediate_link_target(entry), self.central / "demo")
        self.assertEqual(skill_manager.immediate_link_target(self.central / "demo"), repo / "skills" / "demo")

    def test_complete_repository_namespace_is_preserved(self) -> None:
        repo_id, parts = skill_manager.repository_identity("https://git.example.com/team/subgroup/pack.git")
        self.assertEqual(repo_id, "git.example.com/team/subgroup/pack")
        self.assertEqual(parts, ["git.example.com", "team", "subgroup", "pack"])

    def test_project_commands_reject_missing_roots_before_any_writes(self) -> None:
        write_skill(self.central / "local-skill")
        config_before = (self.home / ".skill-linker.json").read_bytes()
        wrong_project = self.root / "Xhanzo's_WorkSpace" / "项目"
        commands = [
            ("install-repo", ["--repo-url", str(self.source), "--skills", "demo=skills/demo", "--enable-project"]),
            ("link", ["--source", str(self.central / "local-skill")]),
            ("link-many", ["--sources", str(self.central / "local-skill")]),
            ("migrate", ["--source", str(self.project / "unused"), "--central", str(self.central)]),
        ]
        for command, arguments in commands:
            for execute in (False, True):
                with self.subTest(command=command, execute=execute):
                    flags = ["--execute"] if execute else []
                    with self.assertRaisesRegex(SystemExit, "项目根目录不存在或不是目录"):
                        self.cli(command, "--project", str(wrong_project), *arguments, *flags)
                    self.assertFalse(wrong_project.parent.exists())
        self.assertFalse((self.central / ".repos").exists())
        self.assertFalse(skill_manager.registry_path(self.central).exists())
        self.assertEqual((self.home / ".skill-linker.json").read_bytes(), config_before)
        with self.assertRaisesRegex(SystemExit, "项目根目录不存在或不是目录"):
            self.cli("check", "--project", str(wrong_project))

    def test_missing_project_cannot_be_created_by_hub_initialization(self) -> None:
        missing = self.root / "missing-project"
        with self.assertRaisesRegex(SystemExit, "项目根目录不存在或不是目录"):
            skill_manager.ensure_project_hub(missing, True)
        self.assertFalse(missing.exists())

    def test_project_file_is_rejected(self) -> None:
        project_file = self.root / "not-a-directory"
        project_file.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "项目根目录不存在或不是目录"):
            self.cli("install-repo", "--project", str(project_file), "--repo-url", str(self.source),
                     "--skills", "demo=skills/demo", "--enable-project", "--execute")
        self.assertEqual(project_file.read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.central / ".repos").exists())

    def test_current_directory_preserves_unicode_project_path_and_reports_landing(self) -> None:
        actual = self.root / "Xhanzo‘s_WorkSpace" / "含空格 项目"
        actual.mkdir(parents=True)
        bind_project(self.home, actual)
        lookalike = self.root / "Xhanzo's_WorkSpace" / "含空格 项目"
        write_skill(self.central / "local-skill")
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", skill_manager.__file__, "link",
             "--project", ".", "--home", str(self.home), "--source", str(self.central / "local-skill"),
             "--link-type", self.link_type, "--execute"],
            cwd=actual, check=True, capture_output=True, text=True, encoding="utf-8",
        )
        marker = '{\n  "verified_project_entries"'
        verified = json.loads(result.stdout[result.stdout.index(marker):])["verified_project_entries"][0]
        self.assertEqual(Path(verified["project"]), actual)
        self.assertEqual(Path(verified["path"]), actual / ".agents" / "skills" / "local-skill")
        self.assertEqual(Path(verified["immediate_target"]), self.central / "local-skill")
        self.assertEqual(verified["skill_name"], "local-skill")
        self.assertTrue((actual / ".agents" / "skills" / "local-skill" / "SKILL.md").is_file())
        self.assertFalse(lookalike.parent.exists())

    def test_verification_rejects_entry_in_a_different_project(self) -> None:
        wrong = self.root / "other-project"
        wrong.mkdir()
        with self.assertRaisesRegex(SystemExit, "不属于计划中的项目"):
            skill_manager.verify_project_entries(self.project, [
                (wrong / ".agents" / "skills" / "demo", self.central / "demo")
            ])


if __name__ == "__main__":
    unittest.main()
