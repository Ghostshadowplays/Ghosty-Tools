"""Exercise the release gate without network calls or real polling delays."""

import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if os.name == "nt":
    GIT_BASH = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
    BASH = str(GIT_BASH) if GIT_BASH.is_file() else None
else:
    BASH = shutil.which("bash")


GH_FIXTURE = r"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$FIXTURE_CALLS"
if [ "$1" = api ]; then
  if [ "$MODE" = api_error ]; then exit 3; fi
  printf '%s\t%s\n' "$AUTO_MERGE" "$SQUASH_MERGE"
  exit 0
fi
workflow=$(printf '%s' "$3" | cut -d= -f2-)
state="$FIXTURE_STATE/$workflow"
count=0
if [ -f "$state" ]; then read -r count < "$state"; fi
count=$((count + 1))
printf '%s\n' "$count" > "$state"
status=completed
conclusion=success
sha=fixture-sha
if [ "$MODE" = rerun_failed ] && [ "$workflow" = security-audit.yml ] && [ "$count" -gt 1 ]; then
  conclusion=failure
fi
if [ "$workflow" = pr-build.yml ]; then
  case "$MODE" in
    progress|rerun_failed)
      if [ "$count" -eq 1 ]; then status="$FIRST_STATUS"; conclusion=pending; fi
      ;;
    missing_then_success)
      if [ "$count" -eq 1 ]; then exit 0; fi
      ;;
    failed) conclusion="$RESULT_CONCLUSION" ;;
    stale) sha=wrong-commit ;;
    never) status=in_progress; conclusion=pending ;;
    missing) exit 0 ;;
    api_error) echo 'Fixture API error' >&2; exit 3 ;;
    unknown) status=unexpected ;;
  esac
fi
printf '%s\t%s\t%s\thttps://example.invalid/run\n' "$status" "$conclusion" "$sha"
"""


@dataclass
class GateResult:
    returncode: int
    stdout: str
    stderr: str
    calls: list[str]
    sleeps: list[str]
    summary: str


@unittest.skipUnless(BASH, "Bash is required to exercise the GitHub release gate")
class ReleaseGateTests(unittest.TestCase):
    def run_gate(self, mode="success", script_name="wait-for-release-checks.sh", **overrides) -> GateResult:
        shell = BASH
        if shell is None:
            raise unittest.SkipTest("Bash is required")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            commands = folder / "bin"
            commands.mkdir()
            state = folder / "state"
            state.mkdir()
            calls = folder / "gh-calls"
            sleeps = folder / "sleeps"
            summary = folder / "summary"
            calls.touch()
            sleeps.touch()
            summary.touch()
            scripts = {
                "gh": GH_FIXTURE,
                "git": "#!/usr/bin/env bash\nprintf 'fixture-sha\\n'\n",
                "sleep": '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$FIXTURE_SLEEPS"\n',
                "timeout": '#!/usr/bin/env bash\nshift\nexec "$@"\n',
            }
            for name, body in scripts.items():
                command = commands / name
                command.write_text(body, encoding="utf-8", newline="\n")
                command.chmod(0o755)
            command_path = commands.as_posix()
            if os.name == "nt":
                command_path = "/" + command_path[0].lower() + command_path[2:]
            environment = {
                **os.environ,
                "MODE": mode,
                "FIRST_STATUS": "in_progress",
                "RESULT_CONCLUSION": "failure",
                "AUTO_MERGE": "true",
                "SQUASH_MERGE": "true",
                "GITHUB_REPOSITORY": "Ghostshadowplays/Ghosty-Tools",
                "GITHUB_SERVER_URL": "https://github.com",
                "GITHUB_STEP_SUMMARY": summary.as_posix(),
                "FIXTURE_STATE": state.as_posix(),
                "FIXTURE_CALLS": calls.as_posix(),
                "FIXTURE_SLEEPS": sleeps.as_posix(),
                "RELEASE_CHECK_TIMEOUT_SECONDS": "2400",
                **overrides,
            }
            result = subprocess.run(
                [shell, "--noprofile", "--norc", "-c",
                 'export PATH="$1:$PATH"; exec bash "$2"', "release-gate-test",
                 command_path, (ROOT / ".github/scripts" / script_name).as_posix()],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=20,
            )
            return GateResult(
                result.returncode, result.stdout, result.stderr,
                calls.read_text(encoding="utf-8").splitlines(),
                sleeps.read_text(encoding="utf-8").splitlines(),
                summary.read_text(encoding="utf-8"),
            )

    def assert_passed(self, result: GateResult):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("All required workflows passed on fixture-sha", result.stdout)
        for call in result.calls:
            self.assertIn("--commit fixture-sha", call)
            self.assertIn("--branch main", call)
            self.assertIn("--event push", call)

    def test_completed_successes_pass_without_waiting(self):
        result = self.run_gate()
        self.assert_passed(result)
        self.assertEqual(len(result.calls), 5)
        self.assertEqual(result.sleeps, [])

    def test_unfinished_states_wait_until_success(self):
        for status in ("queued", "requested", "waiting", "pending", "in_progress"):
            with self.subTest(status=status):
                result = self.run_gate("progress", FIRST_STATUS=status)
                self.assert_passed(result)
                self.assertEqual(result.sleeps, ["30"])
                self.assertEqual(len(result.calls), 10)

    def test_run_not_yet_registered_is_retried(self):
        result = self.run_gate("missing_then_success")
        self.assert_passed(result)
        self.assertIn("waiting for its push run to appear", result.stdout)

    def test_unsuccessful_completed_runs_fail_immediately(self):
        for conclusion in ("failure", "cancelled", "timed_out", "skipped", "action_required"):
            with self.subTest(conclusion=conclusion):
                result = self.run_gate("failed", RESULT_CONCLUSION=conclusion)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("finished with " + conclusion, result.stdout)
                self.assertEqual(result.sleeps, [])

    def test_stale_success_does_not_pass_for_the_selected_commit(self):
        result = self.run_gate("stale")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("instead of fixture-sha", result.stdout)

    def test_pending_run_times_out_with_workflow_name(self):
        result = self.run_gate("never", RELEASE_CHECK_TIMEOUT_SECONDS="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Timed out after 0 seconds waiting for: pr-build.yml", result.stdout)
        self.assertEqual(result.sleeps, [])

    def test_missing_run_times_out(self):
        result = self.run_gate("missing", RELEASE_CHECK_TIMEOUT_SECONDS="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Timed out", result.stdout)

    def test_api_error_fails_without_mistaking_it_for_a_missing_run(self):
        result = self.run_gate("api_error")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not query pr-build.yml", result.stdout)

    def test_earlier_success_is_checked_again_while_other_builds_run(self):
        result = self.run_gate("rerun_failed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("security-audit.yml finished with failure", result.stdout)

    def test_unknown_status_fails(self):
        result = self.run_gate("unknown")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected status", result.stdout)

    def test_invalid_timeout_is_reported(self):
        result = self.run_gate(RELEASE_CHECK_TIMEOUT_SECONDS="invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be non-negative integers", result.stdout)
        self.assertEqual(result.calls, [])

    def test_leading_zero_intervals_are_decimal(self):
        result = self.run_gate(
            "progress", RELEASE_CHECK_TIMEOUT_SECONDS="0040",
            RELEASE_CHECK_POLL_SECONDS="0008",
        )
        self.assert_passed(result)
        self.assertIn("Waiting up to 40 seconds", result.stdout)
        self.assertEqual(result.sleeps, ["8"])

    def test_release_settings_allow_enabled_auto_and_squash_merge(self):
        result = self.run_gate(script_name="check-release-settings.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(result.calls), 1)
        self.assertTrue(result.calls[0].startswith("api repos/Ghostshadowplays/Ghosty-Tools "))
        self.assertEqual(result.sleeps, [])

    def test_disabled_auto_merge_gives_settings_link_and_recovery_steps(self):
        result = self.run_gate(script_name="check-release-settings.sh", AUTO_MERGE="false")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Enable 'Allow auto-merge'", result.stdout)
        self.assertIn("https://github.com/Ghostshadowplays/Ghosty-Tools/settings", result.summary)
        self.assertIn("existing open release PR will be reused", result.summary)
        self.assertEqual(len(result.calls), 1)

    def test_disabled_squash_merge_is_reported(self):
        result = self.run_gate(script_name="check-release-settings.sh", SQUASH_MERGE="false")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Enable 'Allow squash merging'", result.stdout)

    def test_both_disabled_merge_settings_are_reported(self):
        result = self.run_gate(
            script_name="check-release-settings.sh", AUTO_MERGE="false", SQUASH_MERGE="false",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Enable 'Allow auto-merge'", result.stdout)
        self.assertIn("Enable 'Allow squash merging'", result.stdout)

    def test_settings_api_failure_is_actionable(self):
        result = self.run_gate("api_error", script_name="check-release-settings.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not read release settings", result.stdout)
        self.assertIn("GH_PAT repository access", result.stdout)
