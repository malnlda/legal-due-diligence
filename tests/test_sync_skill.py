from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_skill.py"
SPEC = importlib.util.spec_from_file_location("sync_skill", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
sync_skill = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync_skill
SPEC.loader.exec_module(sync_skill)


class SyncSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source"
        self.target = self.root / "target"

        self._write("SKILL.md", "version: 0.5.1\n")
        self._write("agents/openai.yaml", "interface: {}\n")
        self._write("references/rule.md", "canonical rule\n")

    def _write(self, relative: str, content: str) -> Path:
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_copies_runtime_package_and_excludes_development_files(self) -> None:
        self._write("README.md", "developer documentation\n")
        self._write("scripts/helper.py", "pass\n")
        self._write("tests/test_other.py", "pass\n")
        self._write(".git/config", "git data\n")
        self._write("references/__pycache__/cache.pyc", "cache\n")
        self._write("references/.DS_Store", "finder data\n")

        sync_skill.synchronize_target(self.source, self.target)

        self.assertEqual(
            (self.target / "SKILL.md").read_text(encoding="utf-8"),
            "version: 0.5.1\n",
        )
        self.assertTrue((self.target / "agents/openai.yaml").is_file())
        self.assertTrue((self.target / "references/rule.md").is_file())
        self.assertFalse((self.target / "README.md").exists())
        self.assertFalse((self.target / "scripts").exists())
        self.assertFalse((self.target / "tests").exists())
        self.assertFalse((self.target / ".git").exists())
        self.assertFalse((self.target / "references/__pycache__").exists())
        self.assertFalse((self.target / "references/.DS_Store").exists())

    def test_sync_removes_stale_and_canonically_deleted_files(self) -> None:
        deleted_source = self._write("references/deleted.md", "old rule\n")
        sync_skill.synchronize_target(self.source, self.target)
        (self.target / "local-stale.txt").write_text("stale\n", encoding="utf-8")
        deleted_source.unlink()

        differences = sync_skill.synchronize_target(self.source, self.target)

        self.assertIn(
            sync_skill.Difference("stale", "local-stale.txt"), differences
        )
        self.assertIn(
            sync_skill.Difference("stale", "references/deleted.md"), differences
        )
        self.assertFalse((self.target / "local-stale.txt").exists())
        self.assertFalse((self.target / "references/deleted.md").exists())
        self.assertEqual(sync_skill.compare_target(self.source, self.target), [])

    def test_check_detects_missing_modified_and_stale_entries(self) -> None:
        sync_skill.synchronize_target(self.source, self.target)
        (self.target / "SKILL.md").write_text("changed\n", encoding="utf-8")
        (self.target / "agents/openai.yaml").unlink()
        (self.target / "stale.txt").write_text("stale\n", encoding="utf-8")

        differences = sync_skill.compare_target(self.source, self.target)

        self.assertIn(sync_skill.Difference("modified", "SKILL.md"), differences)
        self.assertIn(
            sync_skill.Difference("missing", "agents/openai.yaml"), differences
        )
        self.assertIn(sync_skill.Difference("stale", "stale.txt"), differences)

    def test_check_mode_returns_nonzero_for_drift_and_zero_when_synced(self) -> None:
        skills_dir = self.root / "codex-skills"
        with redirect_stdout(io.StringIO()):
            drift_status = sync_skill.main(
                ["--check", "--codex-skills-dir", str(skills_dir)],
                source_root=self.source,
                environ={},
            )
            sync_status = sync_skill.main(
                ["--codex-skills-dir", str(skills_dir)],
                source_root=self.source,
                environ={},
            )
            clean_status = sync_skill.main(
                ["--check", "--codex-skills-dir", str(skills_dir)],
                source_root=self.source,
                environ={},
            )

        self.assertEqual(drift_status, 1)
        self.assertEqual(sync_status, 0)
        self.assertEqual(clean_status, 0)

    def test_default_codex_targets_use_injected_home_agents_skills(self) -> None:
        for label, arguments in (("implicit", []), ("flag", ["--codex"])):
            with self.subTest(label=label):
                home = self.root / f"{label}-home"
                with redirect_stdout(io.StringIO()):
                    status = sync_skill.main(
                        arguments,
                        source_root=self.source,
                        environ={"HOME": str(home)},
                    )

                self.assertEqual(status, 0)
                self.assertTrue(
                    (
                        home
                        / ".agents/skills/legal-due-diligence/SKILL.md"
                    ).is_file()
                )
                self.assertFalse((home / ".codex").exists())

    def test_installs_codex_hermes_and_optional_claude_targets(self) -> None:
        codex_skills_dir = self.root / "codex-skills"
        hermes_home = self.root / "hermes-profile"
        claude_home = self.root / "claude"

        with redirect_stdout(io.StringIO()):
            status = sync_skill.main(
                [
                    "--codex-skills-dir",
                    str(codex_skills_dir),
                    "--hermes-home",
                    str(hermes_home),
                    "--claude-home",
                    str(claude_home),
                ],
                source_root=self.source,
                environ={},
            )

        self.assertEqual(status, 0)
        self.assertTrue(
            (codex_skills_dir / "legal-due-diligence/SKILL.md").is_file()
        )
        self.assertTrue(
            (
                hermes_home
                / "skills/legal/legal-due-diligence/SKILL.md"
            ).is_file()
        )
        self.assertTrue(
            (claude_home / "skills/legal-due-diligence/SKILL.md").is_file()
        )

    def test_hermes_flag_uses_explicit_environment_home(self) -> None:
        hermes_home = self.root / "ophilia"

        with redirect_stdout(io.StringIO()):
            status = sync_skill.main(
                ["--hermes"],
                source_root=self.source,
                environ={"HERMES_HOME": str(hermes_home)},
            )

        self.assertEqual(status, 0)
        self.assertTrue(
            (
                hermes_home
                / "skills/legal/legal-due-diligence/SKILL.md"
            ).is_file()
        )

    def test_dry_run_does_not_write(self) -> None:
        differences = sync_skill.synchronize_target(
            self.source, self.target, dry_run=True
        )

        self.assertEqual(differences, [sync_skill.Difference("missing target", ".")])
        self.assertFalse(self.target.exists())

    def test_repository_version_fields_are_consistent(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        skill_text = (repository / "SKILL.md").read_text(encoding="utf-8")
        readme_text = (repository / "README.md").read_text(encoding="utf-8")
        changelog_text = (repository / "CHANGELOG.md").read_text(encoding="utf-8")
        agent_text = (repository / "agents/openai.yaml").read_text(encoding="utf-8")

        skill_version = re.search(
            r'^  version: "([^"]+)"$', skill_text, flags=re.MULTILINE
        )
        readme_version = re.search(r"当前版本 `([^`]+)`", readme_text)
        changelog_version = re.search(
            r"^## ([^ ]+) - ", changelog_text, flags=re.MULTILINE
        )
        self.assertIsNotNone(skill_version)
        self.assertIsNotNone(readme_version)
        self.assertIsNotNone(changelog_version)
        assert skill_version and readme_version and changelog_version
        expected = skill_version.group(1)
        self.assertEqual(readme_version.group(1), expected)
        self.assertEqual(changelog_version.group(1), expected)

        agent_version = re.search(
            r'^\s*version:\s*["\']?([^"\'\s]+)', agent_text, flags=re.MULTILINE
        )
        if agent_version is not None:
            self.assertEqual(agent_version.group(1), expected)


if __name__ == "__main__":
    unittest.main()
