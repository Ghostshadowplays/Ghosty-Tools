#!/usr/bin/env bash
set -euo pipefail

if ! [[ "${VERSION:-}" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo "::error::VERSION must be a release version such as v8.0.7."
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "::error::Prepare the release branch before changing version files."
  exit 1
fi

# HEAD is the main commit that passed the release checks, even if main advances.
source_commit=$(git rev-parse HEAD)
branch="release/$VERSION"

if git ls-remote --exit-code origin "refs/heads/$branch" > /dev/null; then
  # A failed run or a closed PR can leave a branch behind. Keep its commits and
  # add the checked main commit so the later push remains a fast-forward.
  git fetch --no-tags origin "refs/heads/$branch"
  git switch --detach FETCH_HEAD
  if ! git merge-base --is-ancestor "$source_commit" HEAD; then
    if ! git merge --no-ff -S -m "chore: sync main into $branch" "$source_commit"; then
      git merge --abort || true
      echo "::error::Could not merge the checked main commit into $branch. Resolve any conflicts or signing errors and start a new monthly release run."
      exit 1
    fi
    git verify-commit HEAD
  fi
  echo "Reusing $branch with the checked main commit $source_commit."
else
  status=$?
  if [ "$status" -ne 2 ]; then
    echo "::error::Could not query $branch on origin; no release branch was prepared."
    exit 1
  fi
  git switch --detach "$source_commit"
  echo "Preparing new branch $branch from $source_commit."
fi
