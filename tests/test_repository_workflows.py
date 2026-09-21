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

from test_skill_manager import init_git_repo, skill_manager, write_config, write_skill


class RepositoryWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.central = self.home / ".e8-skill-linker" / "AgentSkills"
        self.central.mkdir(parents=True)
        self.project.mkdir()
        write_config(self.home / ".skill-linker.json", self.central)
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

    def install(self, specs: str = "demo=skills/demo", library: str = "personal") -> Path:
        self.cli("install-repo", "--repo-url", str(self.source), "--skills", specs,
                 "--library", library, "--link-type", self.link_type, "--execute")
        central = skill_manager.configured_central(self.project, self.home, library)
        record = next(iter(skill_manager.read_registry(central)["repositories"].values()))
        return central / record["path"]

    def add_work(self) -> Path:
        self.cli("library-add", "--scope", "user", "--name", "work", "--central-base", str(self.root / "work"), "--execute")
        return self.root / "work" / ".e8-skill-linker" / "AgentSkills"

    def test_project_link_preserves_central_entry_after_retarget(self) -> None:
        self.project = self.root / "含空格 项目"
        self.project.mkdir()
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

    def test_root_skill_name_may_differ_from_repository_name(self) -> None:
        (self.source / "SKILL.md").write_text("---\nname: root-writer\ndescription: test\n---\n", encoding="utf-8")
        self.commit("root skill")
        self.install("root-writer=.")
        self.assertTrue((self.central / "root-writer" / "SKILL.md").is_file())

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
        self.cli("update", "--repo", str(repo), "--library", "personal", "--execute")
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
        self.assertEqual({row["library"] for row in json.loads(output)["repositories"]}, {"personal", "work"})
        code, output = self.cli("check", "--all-libraries")
        self.assertEqual(code, 0, output)

    def test_project_config_does_not_fall_back_to_user_named_libraries(self) -> None:
        self.add_work()
        write_config(self.project / ".skill-linker.json", self.central)
        with self.assertRaisesRegex(SystemExit, "不存在中央库"):
            self.cli("updates", "--library", "work")

    def test_switch_reports_existing_project_ownership_without_relinking(self) -> None:
        self.add_work()
        self.install()
        self.cli("link", "--source", str(self.central / "demo"), "--link-type", self.link_type, "--execute")
        _, output = self.cli("library-use", "--scope", "user", "--name", "work", "--execute")
        plan, _ = json.JSONDecoder().raw_decode(output)
        self.assertEqual(plan["planned_library_use"]["existing_project_links"][0]["libraries"], ["personal"])
        self.assertEqual(skill_manager.immediate_link_target(self.project / ".agents" / "skills" / "demo"), self.central / "demo")

    def test_check_fails_when_registered_skill_or_commit_is_missing(self) -> None:
        repo = self.install()
        (repo / "skills" / "demo" / "SKILL.md").unlink()
        code, output = self.cli("check", "--library", "personal")
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

    def test_complete_repository_namespace_is_preserved(self) -> None:
        repo_id, parts = skill_manager.repository_identity("https://git.example.com/team/subgroup/pack.git")
        self.assertEqual(repo_id, "git.example.com/team/subgroup/pack")
        self.assertEqual(parts, ["git.example.com", "team", "subgroup", "pack"])


if __name__ == "__main__":
    unittest.main()
