"""Exercise monthly release retries using local Git remotes and fixture SSH keys."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")
SSH_KEYGEN = shutil.which("ssh-keygen")
if os.name == "nt":
    GIT_BASH = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
    BASH = str(GIT_BASH) if GIT_BASH.is_file() else None
else:
    BASH = shutil.which("bash")


@unittest.skipUnless(BASH and GIT and SSH_KEYGEN, "Git, Bash and ssh-keygen are required")
class ReleaseBranchTests(unittest.TestCase):
    def setUp(self):
        if not BASH or not GIT or not SSH_KEYGEN:
            self.skipTest("Git, Bash and ssh-keygen are required")
        self.bash = BASH
        self.git = GIT
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.work = self.folder / "release work"
        self.work.mkdir()
        self.remote = self.folder / "origin.git"
        self.environment = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_MERGE_AUTOEDIT": "no",
            "VERSION": "v8.0.7",
        }
        self.run_git("init", "--bare", "--initial-branch=main", str(self.remote))
        self.run_git("init", "--initial-branch=main")
        self.run_git("config", "user.name", "Release fixture")
        self.run_git("config", "user.email", "fixture@example.invalid")
        self.run_git("config", "core.autocrlf", "false")
        self.run_git("remote", "add", "origin", str(self.remote))
        self.commit_file("version.txt", "v8.0.6\n")
        self.run_git("push", "origin", "main")

        key = self.folder / "signing_key"
        subprocess.run(
            [SSH_KEYGEN, "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            env=self.environment, check=True, capture_output=True, text=True, timeout=20,
        )
        allowed = self.folder / "allowed_signers"
        allowed.write_text(
            "fixture@example.invalid " + key.with_suffix(".pub").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.run_git("config", "gpg.format", "ssh")
        self.run_git("config", "user.signingkey", key.as_posix())
        self.run_git("config", "gpg.ssh.allowedSignersFile", allowed.as_posix())
        self.run_git("config", "commit.gpgsign", "true")

    def run_git(self, *arguments, check=True):
        return subprocess.run(
            [self.git, *arguments], cwd=self.work, env=self.environment,
            check=check, capture_output=True, text=True, timeout=20,
        )

    def commit_file(self, name, content):
        (self.work / name).write_text(content, encoding="utf-8")
        self.run_git("add", name)
        self.run_git("commit", "-m", f"Update {name}")
        return self.run_git("rev-parse", "HEAD").stdout.strip()

    def prepare(self):
        return subprocess.run(
            [self.bash, (ROOT / ".github/scripts/prepare-release-branch.sh").as_posix()],
            cwd=self.work, env=self.environment, capture_output=True, text=True, timeout=20,
        )

    def create_leftover_release(self):
        self.run_git("switch", "-c", "release/v8.0.7")
        release = self.commit_file("version.txt", "v8.0.7\n")
        self.run_git("push", "origin", "HEAD:refs/heads/release/v8.0.7")
        self.run_git("switch", "main")
        return release

    def remote_release(self):
        return self.run_git("ls-remote", "origin", "refs/heads/release/v8.0.7").stdout.split()[0]

    def assert_prepared(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_new_release_starts_from_the_checked_main_commit(self):
        source = self.run_git("rev-parse", "HEAD").stdout.strip()
        self.assert_prepared(self.prepare())
        self.assertEqual(self.run_git("rev-parse", "HEAD").stdout.strip(), source)
        release = self.commit_file("version.txt", "v8.0.7\n")
        self.run_git("verify-commit", "HEAD")
        self.run_git("push", "origin", "HEAD:refs/heads/release/v8.0.7")
        self.assertEqual(self.remote_release(), release)

    def test_leftover_branch_keeps_its_commits_and_gets_a_signed_main_merge(self):
        release = self.create_leftover_release()
        source = self.commit_file("latest-fix.txt", "Include the latest main fix.\n")
        # A newer remote main must not replace the commit that passed the gate.
        later = self.commit_file("unchecked.txt", "Not checked by this run.\n")
        self.run_git("push", "origin", "main")
        self.run_git("switch", "--detach", source)
        self.assert_prepared(self.prepare())
        self.assertEqual(self.run_git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()[1:],
                         [release, source])
        self.assertEqual((self.work / "version.txt").read_text(encoding="utf-8"), "v8.0.7\n")
        self.assertTrue((self.work / "latest-fix.txt").exists())
        self.assertFalse((self.work / "unchecked.txt").exists())
        self.run_git("verify-commit", "HEAD")
        self.run_git("push", "origin", "HEAD:refs/heads/release/v8.0.7")
        self.assertEqual(self.remote_release(), self.run_git("rev-parse", "HEAD").stdout.strip())
        self.assertEqual(self.run_git("rev-parse", "main").stdout.strip(), later)

    def test_unchanged_retry_reuses_the_existing_release_commit(self):
        release = self.create_leftover_release()
        for _ in range(2):
            self.run_git("switch", "main")
            self.assert_prepared(self.prepare())
            self.assertEqual(self.run_git("rev-parse", "HEAD").stdout.strip(), release)
            self.assertEqual(self.run_git("status", "--porcelain").stdout, "")
            self.run_git("push", "origin", "HEAD:refs/heads/release/v8.0.7")
            self.assertEqual(self.remote_release(), release)

    def test_conflict_stops_without_changing_the_remote_branch(self):
        release = self.create_leftover_release()
        source = self.commit_file("version.txt", "Conflicting main change.\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Resolve any conflicts", result.stdout)
        self.assertEqual(self.remote_release(), release)
        self.assertEqual(self.run_git("rev-parse", "main").stdout.strip(), source)
        self.assertEqual(self.run_git("status", "--porcelain").stdout, "")

    def test_unavailable_remote_is_not_treated_as_an_absent_branch(self):
        self.run_git("remote", "set-url", "origin", str(self.folder / "missing.git"))
        source = self.run_git("rev-parse", "HEAD").stdout.strip()
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not query release/v8.0.7", result.stdout)
        self.assertEqual(self.run_git("rev-parse", "HEAD").stdout.strip(), source)

    def test_concurrent_remote_update_is_preserved_by_the_normal_push(self):
        release = self.create_leftover_release()
        self.run_git("switch", "-c", "concurrent", release)
        concurrent = self.commit_file("other-change.txt", "Another contributor's change.\n")
        self.run_git("switch", "main")
        self.commit_file("latest-fix.txt", "Main fix.\n")
        self.assert_prepared(self.prepare())
        self.run_git("push", "origin", f"{concurrent}:refs/heads/release/v8.0.7")
        push = self.run_git("push", "origin", "HEAD:refs/heads/release/v8.0.7", check=False)
        self.assertNotEqual(push.returncode, 0)
        self.assertEqual(self.remote_release(), concurrent)


if __name__ == "__main__":
    unittest.main()
