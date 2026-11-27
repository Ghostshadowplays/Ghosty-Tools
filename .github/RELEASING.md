# Releases

The monthly workflow runs at 00:00 UTC on the first day of each month. It skips
the release when there are no commits since the latest version tag.

1. `monthly-release.yml` verifies that CI, the security audit and CodeQL passed
   for the current main commit. It chooses the next patch version above both
   the latest version tag and `config/version.json`, updates the three version
   files, and opens an SSH-signed release PR.
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
- Keep the existing `GH_PAT`, `RELEASE_SSH_PRIVATE_KEY`, `RELEASE_GIT_EMAIL`,
  `CERT_PFX` and `CERT_PASSWORD` secrets. The PAT creates the PR and enables
  auto-merge so the resulting push and PR events can start checks/workflows.
- Allow the Actions token to create tags and releases under the repository's
  rules. The publish/build workflows request `contents: write`.

The Windows signer is self-signed. The build imports its public certificate
into the temporary runner's current-user root store, then requires a valid
Authenticode signature, the expected signer thumbprint and a timestamp.
This does not make the certificate trusted on users' computers.

## Manual builds and recovery

- To test the current code, run **Build and Release EXE** on `main` with
  `tag_name` blank. The version comes from `config/version.json`. Download the
  platform artifacts from the run's summary; this mode does not publish.
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
