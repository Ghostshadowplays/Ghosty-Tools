"""Check release-document migration, archival and retries without GitHub access."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core.release_notes import bundled_release_notes


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_release_docs", ROOT / ".github/scripts/update-release-docs.py")
if SPEC is None or SPEC.loader is None:
    raise ImportError("Cannot load the release documentation updater")
DOCS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOCS)

LEGACY = """# Ghosty Tools

Keep this introduction.

## 🆕 What's New in v8.0.7

- Previous release feature.

[Full v8.0.5 changelog](https://example.invalid/old-comparison)

## 🆕 What's New in v8.0.4

- Historical driver fix.

## Features

Keep the features and installation instructions.
"""


class ReleaseDocumentationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.readme = self.root / "README.md"
        self.readme.write_text(LEGACY, encoding="utf-8")
        self.notes = self.root / "config/release_notes"
        self.notes.mkdir(parents=True)
        (self.notes / "v8.0.6.md").write_text(
            "# What's New in v8.0.6\n\n## Workspace\n\n- Existing curated notes.\n", encoding="utf-8",
        )

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def update(self, version="v8.0.9", notes="## What's Changed\n\n- A new release feature.", commits=""):
        DOCS.update_release_docs(self.root, version, notes, commit_notes=commits)

    def test_existing_readme_entries_are_archived_without_losing_other_sections(self):
        self.update()
        readme = self.readme.read_text(encoding="utf-8")
        history = (self.root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count("## 🆕 What's New in"), 1)
        self.assertIn("## 🆕 What's New in v8.0.9", readme)
        self.assertIn("### What's Changed", readme)
        self.assertIn("Keep this introduction.", readme)
        self.assertTrue(readme.endswith("## Features\n\nKeep the features and installation instructions.\n"))
        self.assertIn("Previous release feature.", (self.notes / "v8.0.7.md").read_text(encoding="utf-8"))
        self.assertIn("Historical driver fix.", (self.notes / "v8.0.4.md").read_text(encoding="utf-8"))
        self.assertIn("Existing curated notes.", history)
        self.assertNotIn("Full v8.0.5 changelog", history)
        positions = [history.index(f"## {version}") for version in ("v8.0.9", "v8.0.7", "v8.0.6", "v8.0.4")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("[Release history](CHANGELOG.md)", readme)

    def test_retries_are_idempotent_and_later_releases_preserve_history(self):
        self.update()
        original = self.files()
        self.update()
        self.assertEqual(self.files(), original)
        self.update("v8.0.10", "- Next month.")
        readme = self.readme.read_text(encoding="utf-8")
        history = (self.root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertNotIn("What's New in v8.0.9", readme)
        self.assertIn("A new release feature.", history)
        self.assertLess(history.index("## v8.0.10"), history.index("## v8.0.9"))
        self.assertEqual((self.notes / "v8.0.9.md").read_bytes(), original["config/release_notes/v8.0.9.md"])

    def test_generated_notes_refresh_when_a_retry_includes_new_changes(self):
        self.update()
        self.update(notes="- Additional checked fix.")
        for path in (self.readme, self.root / "CHANGELOG.md", self.notes / "v8.0.9.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Additional checked fix.", text)
            self.assertNotIn("A new release feature.", text)

    def test_older_release_cannot_replace_the_latest_readme(self):
        self.update()
        before = self.files()
        with self.assertRaisesRegex(ValueError, "older release"):
            self.update("v8.0.8", "- An older published release.")
        self.assertEqual(self.files(), before)

    def test_direct_commits_supply_notes_when_github_only_returns_a_comparison(self):
        comparison = "**Full Changelog**: https://example.invalid/compare/v8.0.8...v8.0.9"
        self.update(notes=comparison, commits="- Improve appearance controls (abc1234)")
        readme = self.readme.read_text(encoding="utf-8")
        self.assertIn("Improve appearance controls", readme)
        self.assertIn(comparison, readme)
        self.update(notes="- A merged PR feature.", commits="- Avoid duplicating the PR commits.")
        self.assertNotIn("Avoid duplicating", self.readme.read_text(encoding="utf-8"))

    def test_hand_written_notes_are_preserved_and_available_to_the_app(self):
        path = self.notes / "v8.0.9.md"
        curated = "# What's New in v8.0.9\n\n## Highlights\n\n- Hand-written explanation.\n"
        path.write_text(curated, encoding="utf-8")
        self.update()
        self.assertEqual(path.read_text(encoding="utf-8"), curated)
        self.assertIn("Hand-written explanation.", self.readme.read_text(encoding="utf-8"))
        with patch("src.core.release_notes.get_resource_path", side_effect=lambda name: str(self.root / name)):
            self.assertEqual(bundled_release_notes("v8.0.9"), curated)

    def test_invalid_markers_or_versions_fail_without_writing_any_files(self):
        for readme in (LEGACY + DOCS.START, DOCS.END + LEGACY + DOCS.START,
                       DOCS.START + DOCS.START + DOCS.END + LEGACY):
            with self.subTest(readme=readme):
                self.readme.write_text(readme, encoding="utf-8")
                before = self.files()
                with self.assertRaises(ValueError):
                    self.update()
                self.assertEqual(self.files(), before)
        self.readme.write_text(LEGACY, encoding="utf-8")
        for version in ("../../outside", "v08.0.9", "8.0.9", "v8.0.9-beta"):
            with self.subTest(version=version):
                before = self.files()
                with self.assertRaises(ValueError):
                    self.update(version)
                self.assertEqual(self.files(), before)

    def test_empty_or_control_marker_notes_fail_without_removing_old_notes(self):
        for body in ("", "  \n ", f"Some notes\n{DOCS.END}"):
            with self.subTest(body=body):
                before = self.files()
                with self.assertRaises(ValueError):
                    self.update(notes=body)
                self.assertEqual(self.files(), before)

    def test_missing_section_is_inserted_and_code_examples_are_preserved(self):
        self.readme.write_text("# Ghosty Tools\n\nIntro.\n\n## Features\n\nDetails.\n", encoding="utf-8")
        notes = "## Examples\n\n```powershell\n# Keep this comment\n## And this one\n```"
        self.update(notes=notes)
        readme = self.readme.read_text(encoding="utf-8")
        self.assertLess(readme.index(DOCS.START), readme.index("## Features"))
        self.assertIn("### Examples", readme)
        self.assertIn("```powershell\n# Keep this comment\n## And this one\n```", readme)


if __name__ == "__main__":
    unittest.main()
