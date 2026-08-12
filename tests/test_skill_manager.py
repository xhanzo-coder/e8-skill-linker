from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "e8-skill-linker" / "scripts" / "skill_manager.py"
SPEC = importlib.util.spec_from_file_location("skill_manager", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"无法加载脚本: {SCRIPT_PATH}")
skill_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill_manager)


def write_skill(path: Path, name: str | None = None) -> None:
    path.mkdir(parents=True)
    skill_name = name or path.name
    (path / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: test\n---\n",
        encoding="utf-8",
    )


def write_config(path: Path, central: Path, mode: str = "centralize") -> None:
    path.write_text(
        json.dumps(
            {"central_skills_dir": str(central), "default_mode": mode},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def init_git_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "E8 Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    (path / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, check=True, capture_output=True, text=True)


class SkillManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.central = self.home / ".e8-skill-linker" / "AgentSkills"
        self.home.mkdir()
        self.project.mkdir()
        self.central.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_project_config_overrides_user_config(self) -> None:
        user_central = self.central
        project_central = self.root / "project-central"
        project_central.mkdir()
        write_config(self.home / ".skill-linker.json", user_central)
        write_config(self.project / ".skill-linker.json", project_central, "ask")

        config = skill_manager.load_effective_config(self.project, self.home)

        self.assertEqual(config["source"], "project")
        self.assertEqual(config["central_skills_dir"], str(project_central))
        self.assertEqual(config["default_mode"], "ask")

    def test_config_rejects_missing_and_unknown_fields(self) -> None:
        config_path = self.project / ".skill-linker.json"

        with self.assertRaisesRegex(ValueError, "缺少必需字段"):
            skill_manager.normalize_config(
                config_path,
                "project",
                {"central_skills_dir": str(self.central)},
                self.home,
            )
        with self.assertRaisesRegex(ValueError, "未知字段"):
            skill_manager.normalize_config(
                config_path,
                "project",
                {
                    "central_skills_dir": str(self.central),
                    "default_mode": "centralize",
                    "extra": True,
                },
                self.home,
            )

    def test_custom_base_derives_namespaced_central_directory(self) -> None:
        custom_base = self.root / "external-drive"
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            central=None,
            central_base=str(custom_base),
            scope="user",
            mode="centralize",
            allow_global_central=False,
            allow_non_namespaced_central=False,
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()):
            result = skill_manager.config(args)

        self.assertEqual(result, 0)
        expected = custom_base / ".e8-skill-linker" / "AgentSkills"
        self.assertTrue(expected.is_dir())
        saved = json.loads((self.home / ".skill-linker.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["central_skills_dir"], str(expected))

    def test_config_dry_run_does_not_write(self) -> None:
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            central=str(self.central),
            central_base=None,
            scope="user",
            mode="centralize",
            allow_global_central=False,
            allow_non_namespaced_central=False,
            execute=False,
        )

        with contextlib.redirect_stdout(io.StringIO()):
            result = skill_manager.config(args)

        self.assertEqual(result, 0)
        self.assertFalse((self.home / ".skill-linker.json").exists())

    def test_link_rejects_source_outside_authorized_roots(self) -> None:
        write_config(self.home / ".skill-linker.json", self.central)
        outside = self.root / "download" / "unsafe-skill"
        write_skill(outside)
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            source=str(outside),
            name=None,
            link_type="auto",
            execute=False,
        )

        with self.assertRaisesRegex(SystemExit, "必须位于已配置中央"):
            skill_manager.link(args)

    def test_config_requires_explicit_confirmation_for_global_central(self) -> None:
        global_central = self.home / ".agents" / "skills"
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            central=str(global_central),
            central_base=None,
            scope="user",
            mode="centralize",
            allow_global_central=False,
            allow_non_namespaced_central=True,
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(
            SystemExit, "--allow-global-central"
        ):
            skill_manager.config(args)

        self.assertFalse(global_central.exists())
        self.assertFalse((self.home / ".skill-linker.json").exists())

    def test_config_requires_explicit_confirmation_for_non_namespaced_central(self) -> None:
        custom_central = self.root / "external-drive" / "AgentSkills"
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            central=str(custom_central),
            central_base=None,
            scope="user",
            mode="centralize",
            allow_global_central=False,
            allow_non_namespaced_central=False,
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(
            SystemExit, "--allow-non-namespaced-central"
        ):
            skill_manager.config(args)

        self.assertFalse(custom_central.exists())
        self.assertFalse((self.home / ".skill-linker.json").exists())

    def test_link_many_preflights_all_sources_before_writing(self) -> None:
        write_config(self.home / ".skill-linker.json", self.central)
        valid = self.central / "valid"
        invalid = self.central / "invalid"
        write_skill(valid)
        invalid.mkdir()
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            sources=f"{valid},{invalid}",
            link_type="auto",
            execute=True,
        )

        with self.assertRaisesRegex(SystemExit, "不包含 SKILL.md"):
            skill_manager.link_many(args)

        self.assertFalse((self.project / ".agents" / "skills" / "valid").exists())

    def test_init_preflights_all_agent_entries_before_writing(self) -> None:
        conflicting = self.project / ".codex" / "skills"
        conflicting.mkdir(parents=True)
        args = argparse.Namespace(
            project=str(self.project),
            agents="claude,codex",
            link_type="auto",
            execute=True,
        )

        with self.assertRaisesRegex(SystemExit, "已有真实路径"):
            skill_manager.init(args)

        self.assertFalse(os.path.lexists(self.project / ".claude" / "skills"))
        self.assertFalse((self.project / ".agents" / "skills").exists())

    def test_init_rejects_invalid_project_hub(self) -> None:
        hub = self.project / ".agents" / "skills"
        hub.parent.mkdir()
        hub.write_text("not a directory\n", encoding="utf-8")
        args = argparse.Namespace(
            project=str(self.project),
            agents="claude,codex",
            link_type="auto",
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(
            SystemExit, "不是可用目录"
        ):
            skill_manager.init(args)

        self.assertFalse(os.path.lexists(self.project / ".claude" / "skills"))
        self.assertFalse(os.path.lexists(self.project / ".codex" / "skills"))

    @unittest.skipIf(os.name == "nt", "Windows CI may not grant symlink permission")
    def test_link_and_unlink_preserve_central_source(self) -> None:
        write_config(self.home / ".skill-linker.json", self.central)
        source = self.central / "writer"
        write_skill(source)
        link_args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            source=str(source),
            name=None,
            link_type="auto",
            execute=True,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            skill_manager.link(link_args)
        target = self.project / ".agents" / "skills" / "writer"
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.resolve(), source.resolve())

        unlink_args = argparse.Namespace(target=str(target), execute=True)
        with contextlib.redirect_stdout(io.StringIO()):
            skill_manager.unlink(unlink_args)
        self.assertFalse(os.path.lexists(target))
        self.assertTrue((source / "SKILL.md").is_file())

    @unittest.skipIf(os.name == "nt", "Windows CI may not grant symlink permission")
    def test_migrate_moves_source_and_leaves_link(self) -> None:
        write_config(self.home / ".skill-linker.json", self.central)
        source = self.project / ".agents" / "skills" / "local-skill"
        write_skill(source)
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            source=str(source),
            central=str(self.central),
            name=None,
            link_type="auto",
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()):
            result = skill_manager.migrate(args)

        target = self.central / "local-skill"
        self.assertEqual(result, 0)
        self.assertTrue(source.is_symlink())
        self.assertEqual(source.resolve(), target.resolve())
        self.assertTrue((target / "SKILL.md").is_file())

    def test_migrate_rolls_back_when_link_creation_fails(self) -> None:
        write_config(self.home / ".skill-linker.json", self.central)
        source = self.project / ".agents" / "skills" / "local-skill"
        write_skill(source)
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            source=str(source),
            central=str(self.central),
            name=None,
            link_type="auto",
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(
            skill_manager, "create_symlink", side_effect=OSError("link failed")
        ), self.assertRaisesRegex(OSError, "link failed"):
            skill_manager.migrate(args)

        self.assertTrue((source / "SKILL.md").is_file())
        self.assertFalse((self.central / "local-skill").exists())

    def test_check_reports_broken_project_link(self) -> None:
        skill_dir = self.project / ".agents" / "skills"
        skill_dir.mkdir(parents=True)
        broken = skill_dir / "broken"
        try:
            broken.symlink_to(self.root / "missing", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"无法在当前环境创建测试软链接: {exc}")
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            include_user=False,
            include_central=False,
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            result = skill_manager.check(args)

        self.assertEqual(result, 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["problems"][0]["name"], "broken")
        self.assertEqual(report["problems"][0]["scope"], "project")

    def test_check_reports_broken_agent_directory_link(self) -> None:
        broken = self.project / ".codex" / "skills"
        broken.parent.mkdir(parents=True)
        try:
            broken.symlink_to(self.root / "missing-hub", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"无法在当前环境创建测试软链接: {exc}")
        args = argparse.Namespace(
            project=str(self.project),
            home=str(self.home),
            include_user=False,
            include_central=False,
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            result = skill_manager.check(args)

        self.assertEqual(result, 1)
        report = json.loads(output.getvalue())
        matches = [item for item in report["problems"] if item["path"] == str(broken)]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0]["broken"])

    def test_windows_auto_falls_back_to_junction(self) -> None:
        link = self.project / "link"
        target = self.central
        with mock.patch.object(skill_manager, "IS_WINDOWS", True), mock.patch.object(
            skill_manager.os, "symlink", side_effect=OSError("permission denied")
        ), mock.patch.object(skill_manager, "create_windows_junction") as junction:
            with contextlib.redirect_stdout(io.StringIO()):
                skill_manager.create_symlink(link, target, True, "auto", [self.central])

        junction.assert_called_once_with(link, target)

    def test_install_self_replace_keeps_backup(self) -> None:
        source = self.root / "source" / "e8-skill-linker"
        write_skill(source, "e8-skill-linker")
        existing = self.home / ".agents" / "skills" / "e8-skill-linker"
        write_skill(existing, "old-copy")
        (existing / "marker.txt").write_text("old", encoding="utf-8")
        args = argparse.Namespace(
            source=str(source),
            home=str(self.home),
            agents="agents",
            mode="copy",
            link_type="auto",
            replace=True,
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()):
            result = skill_manager.install_self(args)

        backups = list(existing.parent.glob("e8-skill-linker.backup-*"))
        self.assertEqual(result, 0)
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "marker.txt").read_text(encoding="utf-8"), "old")
        self.assertEqual((existing / "SKILL.md").read_text(encoding="utf-8"), (source / "SKILL.md").read_text(encoding="utf-8"))

    def test_install_self_rolls_back_when_agent_link_fails(self) -> None:
        source = self.root / "source" / "e8-skill-linker"
        write_skill(source, "e8-skill-linker")
        existing = self.home / ".agents" / "skills" / "e8-skill-linker"
        write_skill(existing, "old-copy")
        (existing / "marker.txt").write_text("old", encoding="utf-8")
        args = argparse.Namespace(
            source=str(source),
            home=str(self.home),
            agents="agents,codex",
            mode="copy",
            link_type="auto",
            replace=True,
            execute=True,
        )

        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(
            skill_manager, "create_symlink", side_effect=OSError("link failed")
        ), self.assertRaisesRegex(OSError, "link failed"):
            skill_manager.install_self(args)

        self.assertEqual((existing / "marker.txt").read_text(encoding="utf-8"), "old")
        self.assertEqual(list(existing.parent.glob("e8-skill-linker.backup-*")), [])
        self.assertFalse(os.path.lexists(self.home / ".codex" / "skills" / "e8-skill-linker"))

    def test_git_status_reports_branch_and_dirty_state(self) -> None:
        repo = self.root / "repo"
        init_git_repo(repo)

        clean = skill_manager.git_status_dict(repo)
        self.assertEqual(clean["branch"], "main")
        self.assertFalse(clean["dirty"])

        (repo / "README.md").write_text("changed\n", encoding="utf-8")
        dirty = skill_manager.git_status_dict(repo)
        self.assertTrue(dirty["dirty"])

    def test_update_fast_forwards_from_upstream(self) -> None:
        repo = self.root / "repo"
        remote = self.root / "remote.git"
        updater = self.root / "updater"
        init_git_repo(repo)
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
        subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote, check=True)
        subprocess.run(["git", "clone", str(remote), str(updater)], check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "E8 Test"], cwd=updater, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=updater, check=True)
        (updater / "README.md").write_text("updated upstream\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "upstream update"], cwd=updater, check=True, capture_output=True, text=True)
        subprocess.run(["git", "push"], cwd=updater, check=True, capture_output=True, text=True)
        args = argparse.Namespace(repo=str(repo), allow_dirty=False, execute=True)

        with contextlib.redirect_stdout(io.StringIO()):
            result = skill_manager.update_repo(args)

        self.assertEqual(result, 0)
        self.assertEqual((repo / "README.md").read_text(encoding="utf-8"), "updated upstream\n")
        self.assertEqual(skill_manager.git_status_dict(repo)["behind"], 0)

    def test_checkout_switches_to_requested_commit(self) -> None:
        repo = self.root / "repo"
        init_git_repo(repo)
        initial_commit = skill_manager.git_output(repo, ["rev-parse", "HEAD"])
        self.assertIsNotNone(initial_commit)
        (repo / "README.md").write_text("second\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "second"], cwd=repo, check=True, capture_output=True, text=True)
        args = argparse.Namespace(repo=str(repo), ref=initial_commit, allow_dirty=False, execute=True)

        with contextlib.redirect_stdout(io.StringIO()):
            result = skill_manager.checkout(args)

        self.assertEqual(result, 0)
        self.assertEqual((repo / "README.md").read_text(encoding="utf-8"), "initial\n")

    def test_clone_discovers_skills_in_local_repository(self) -> None:
        source = self.root / "source-repo"
        init_git_repo(source)
        write_skill(source / "skills" / "demo")
        subprocess.run(["git", "add", "skills/demo/SKILL.md"], cwd=source, check=True)
        subprocess.run(["git", "commit", "-m", "add skill"], cwd=source, check=True, capture_output=True, text=True)
        destination_parent = self.root / "downloads"
        args = argparse.Namespace(
            repo_url=str(source),
            dest_parent=str(destination_parent),
            name="downloaded-skill",
            execute=True,
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = skill_manager.clone(args)

        self.assertEqual(result, 0)
        cloned = destination_parent / "downloaded-skill"
        self.assertTrue((cloned / "skills" / "demo" / "SKILL.md").is_file())
        expected_skill = (cloned / "skills" / "demo").resolve(strict=False)
        discovered = [Path(path).resolve(strict=False) for path in skill_manager.skill_dirs_in_repo(cloned)]
        self.assertEqual(discovered, [expected_skill])

    def test_find_git_repos_does_not_treat_parent_repo_as_central_repo(self) -> None:
        outer = self.root / "outer"
        outer.mkdir()
        subprocess.run(["git", "init"], cwd=outer, check=True, capture_output=True, text=True)
        central = outer / "AgentSkills"
        central.mkdir()

        repos = skill_manager.find_git_repos(central)

        self.assertEqual(repos, [])

    def test_rejects_path_traversal_names_and_option_like_git_refs(self) -> None:
        with self.assertRaisesRegex(SystemExit, "路径穿越"):
            skill_manager.validate_skill_name("../outside")
        with self.assertRaisesRegex(SystemExit, "以 - 开头"):
            skill_manager.validate_git_argument("--help", "checkout ref")


if __name__ == "__main__":
    unittest.main()
