# Releases

The monthly workflow runs at 00:00 UTC on the first day of each month. It skips
the release when there are no commits since the latest version tag.

1. `monthly-release.yml` verifies that CI, the security audit, CodeQL, workflow
   validation and package builds passed for the current main commit. It chooses
   the next patch version above both the latest version tag and
   `config/version.json`, updates the three version files, and opens an
   SSH-signed release PR. Retries reuse an existing release branch, including
   branches left by closed PRs, and merge in the checked main commit with an
   SSH-signed merge commit when needed. Existing open release PRs are updated
   rather than duplicated.
2. The workflow enables squash auto-merge on that PR. GitHub waits for required
   checks and branch rules, including any required reviews.
3. After the PR merges, `publish-release.yml` tags the PR's merge commit and
   calls `release.yml` directly. This does not depend on one workflow's
   `GITHUB_TOKEN` triggering another workflow.
4. The build workflow checks that the tag matches `config/version.json`,
   builds all platforms from the same commit, signs and verifies the Windows
   EXE, and saves build artifacts. After every build and the SBOM succeed, one
   job uploads all eight release assets and publishes the release.

## Repository settings

- Enable **Allow auto-merge** and **Allow squash merging** under repository
  Settings > General > Pull Requests.
  Direct link: https://github.com/Ghostshadowplays/Ghosty-Tools/settings.
  The workflow checks both settings before waiting for builds or creating a PR.
  Enabling these settings requires repository administrator access; the
  workflow does not change repository settings.
- Configure the required PR checks in the rules for `main`. Required human
  reviews still need approval before auto-merge can finish.
- Add `Validate GitHub Actions`, `Build (Windows x64)`, `Build (Linux x64)`
  and `Build (macOS arm64)` as required checks once their first runs have
  completed, so auto-merge waits for workflow validation and packaging too.
- Keep the existing `GH_PAT`, `RELEASE_SSH_PRIVATE_KEY`, `RELEASE_GIT_EMAIL`,
  `CERT_PFX` and `CERT_PASSWORD` secrets. The PAT creates the PR and enables
  auto-merge so the resulting push and PR events can start checks/workflows.
- Allow the Actions token to create tags and releases under the repository's
  rules. The publish/build workflows request `contents: write`.

The Windows signer is self-signed. The build loads the PFX with an ephemeral
private key and uses `certutil -f -addstore Root` to import only its public
certificate into the temporary hosted runner's machine root store. This avoids
the hidden trust confirmation that a current-user root import can show.
The hosted Windows runner has the administrator access this import needs.
The build still requires a valid Authenticode signature, the expected signer
thumbprint and a timestamp. Certificate preparation and verification each have
a three-minute limit; signing has a five-minute limit. This does not make the
certificate trusted on users' computers.

## Checks before release

`workflow-validation.yml` runs actionlint on every workflow, including shell
and embedded Python checks, using the versioned official actionlint container.
`pr-build.yml` builds an unsigned Windows EXE, Linux DEB and macOS arm64 binary
with the release's Python 3.12 and PyInstaller spec. It saves each package and
its SHA256 checksum as a build artifact for seven days.

Both workflows run on PRs into `main`, pushes to `main`, and manual dispatch.
They need no release secrets. New commits cancel older runs for the same PR or
branch. The monthly workflow also requires both checks to pass on its source
commit before opening a release PR.

The monthly release waits up to 40 minutes for all five required push workflows
on its checked-out main commit. It polls every 30 seconds, including while a
workflow is queued, running or not yet listed by GitHub. Completed failures,
cancellations, skipped runs and results for a different commit stop the
release. A timeout lists the workflows that have not finished successfully.

## README and release history

Each monthly release PR updates the marked What's New section in `README.md`
to the new version and rebuilds `CHANGELOG.md` with the full release history.
Previous entries are kept in `config/release_notes/<version>.md`; the first run
also archives the original README entries. Only the latest version appears in
the README. README content outside the marked section is retained.

GitHub generates the default notes from merged PRs since the previous tag,
using the main commit that passed the release checks. For custom highlights,
add or edit `config/release_notes/<version>.md` in the release PR and remove
the `<!-- generated-release-notes -->` marker if present. Hand-written notes
are preserved on retries; generated notes refresh when the source changes.
Run the documentation updater again after editing notes to refresh the README
and changelog, or start a new monthly run for the same pending version.

The signed release commit includes the version files, README, changelog and
notes, so they go through the same PR checks. After merging, the app bundles
those notes and GitHub Release publishing uses that same file. Rebuilding an
older tag without bundled notes still uses GitHub's generated release notes.
The README update lands when the release PR merges; if packaging fails, retry
the Publish Release job to finish publishing that version.

## Manual builds and recovery

- To test the current code, run **Build and Release EXE** on `main` with
  `tag_name` blank. The version comes from `config/version.json`. Download the
  platform artifacts from the run's summary; this mode does not publish.
- For unsigned test packages without signing secrets, run **PR Build Checks**
  and download the platform artifacts from its summary.
- To build or repair an existing release, run **Build and Release EXE** from
  `main` and enter its existing tag, for example `v8.0.6`. The updated workflow
  builds the source at that tag and publishes/uploads its assets. The tag and
  the version file at that tag must agree.
- After a failed merged-PR release, rerun the failed jobs in **Publish Release**.
  An existing tag pointing to that same merge commit is accepted on retries;
  a tag pointing elsewhere is rejected.
- To start the monthly process early, run **Monthly Auto Release** manually.
  Its change detection, checks and auto-merge rules are the same as the schedule.
- If a run failed with `Auto merge is not allowed for this repository`, enable
  **Allow auto-merge** and **Allow squash merging**, then start the monthly
  workflow again. It reuses the existing open `release/<version>` PR and enables
  auto-merge on it. The PR can also be merged in GitHub once its required checks
  and reviews pass; the publish workflow then builds the release.
- If a run failed pushing `release/<version>` with `non-fast-forward`, push
  these workflow changes to `main` and start a new **Monthly Auto Release** run.
  It fetches and reuses the existing branch, preserving its commits while adding
  the checked main changes. If its PR was closed without merging, the workflow
  creates a new PR. An unchanged version bump is accepted on retries. Pushes
  remain fast-forward only; a concurrent branch update requires a new run.
  Merge conflicts stop before pushing and must be resolved on the release
  branch before retrying.

Push these workflow changes to `main` before starting a new run. Rerunning an old
failed run uses its original workflow definition, so it will not pick up these
fixes. If a failed version bump never created its tag, start the monthly workflow
again to release the next patch version.
