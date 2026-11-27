#!/usr/bin/env bash
set -euo pipefail

repository=${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}
settings_url="${GITHUB_SERVER_URL:-https://github.com}/$repository/settings"
if ! settings=$(gh api "repos/$repository" \
  --jq '[.allow_auto_merge // false, .allow_squash_merge // false] | @tsv'); then
  echo "::error::Could not read release settings for $repository. Check GH_PAT repository access."
  exit 1
fi

IFS=$'\t' read -r auto_merge squash_merge <<< "$settings"
failed=false
if [ "$auto_merge" != "true" ]; then
  echo "::error::Enable 'Allow auto-merge' in Settings > General > Pull Requests: $settings_url"
  failed=true
fi
if [ "$squash_merge" != "true" ]; then
  echo "::error::Enable 'Allow squash merging' in Settings > General > Pull Requests: $settings_url"
  failed=true
fi
if [ "$failed" = "true" ]; then
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    {
      echo "### Monthly release needs repository settings"
      echo ""
      echo "Open [Settings > General > Pull Requests]($settings_url) and enable:"
      echo ""
      echo "- **Allow auto-merge**"
      echo "- **Allow squash merging**"
      echo ""
      echo "Keep required checks and reviews on main. Then start Monthly Auto Release again."
      echo "An existing open release PR will be reused."
    } >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 1
fi

echo "Repository settings allow squash auto-merge after required checks and reviews."
