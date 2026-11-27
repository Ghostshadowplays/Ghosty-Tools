# Releases

The monthly workflow runs at 00:00 UTC on the first day of each month. It skips
the release when there are no commits since the latest version tag.

1. `monthly-release.yml` verifies that CI, the security audit, CodeQL, workflow
   validation and package builds passed for the current main commit. It chooses
   the next patch version above both the latest version tag and
   `config/version.json`, updates the three version files, and opens an
   SSH-signed release PR.
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

Push these workflow changes to `main` before starting a new run. Rerunning an old
failed run uses its original workflow definition, so it will not pick up these
fixes. If a failed version bump never created its tag, start the monthly workflow
again to release the next patch version.
