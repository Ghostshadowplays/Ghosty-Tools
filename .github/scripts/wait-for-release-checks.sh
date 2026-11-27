#!/usr/bin/env bash
set -euo pipefail

main_sha=$(git rev-parse HEAD)
wait_seconds=${RELEASE_CHECK_TIMEOUT_SECONDS:-2400}
poll_seconds=${RELEASE_CHECK_POLL_SECONDS:-30}
if ! [[ "$wait_seconds" =~ ^[0-9]+$ && "$poll_seconds" =~ ^[0-9]+$ ]]; then
  echo "::error::Release check timeout and poll interval must be non-negative integers."
  exit 1
fi
wait_seconds=$((10#$wait_seconds))
poll_seconds=$((10#$poll_seconds))
deadline=$((SECONDS + wait_seconds))
workflows=(
  security-audit.yml
  python-app.yml
  codeql.yml
  workflow-validation.yml
  pr-build.yml
)

echo "Waiting up to $wait_seconds seconds for required workflows on $main_sha."
while true; do
  pending=()
  for workflow in "${workflows[@]}"; do
    # Use nonempty TSV fields so Bash preserves a pending run's SHA and URL.
    if ! result=$(timeout 60s gh run list \
      --workflow="$workflow" \
      --branch main \
      --commit "$main_sha" \
      --event push \
      --limit 1 \
      --json conclusion,status,headSha,url \
      --jq '.[0] // empty | [.status, (.conclusion // "" | if . == "" then "pending" else . end), .headSha, .url] | @tsv'); then
      echo "::error::Could not query $workflow for commit $main_sha."
      exit 1
    fi

    if [ -z "$result" ]; then
      echo "$workflow: waiting for its push run to appear on $main_sha."
      pending+=("$workflow")
      continue
    fi

    IFS=$'\t' read -r status conclusion head_sha url <<< "$result"
    echo "$workflow: $status / $conclusion / $head_sha / $url"
    if [ "$head_sha" != "$main_sha" ]; then
      echo "::error::$workflow returned a run for $head_sha instead of $main_sha."
      exit 1
    fi
    case "$status" in
      completed)
        if [ "$conclusion" != "success" ]; then
          echo "::error::$workflow finished with $conclusion on $main_sha. $url"
          exit 1
        fi
        ;;
      queued|in_progress|waiting|pending|requested)
        pending+=("$workflow")
        ;;
      *)
        echo "::error::Unexpected status '$status' for $workflow. $url"
        exit 1
        ;;
    esac
  done

  if [ "${#pending[@]}" -eq 0 ]; then
    echo "All required workflows passed on $main_sha."
    exit 0
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "::error::Timed out after $wait_seconds seconds waiting for: ${pending[*]} (commit $main_sha)."
    exit 1
  fi
  remaining=$((deadline - SECONDS))
  delay=$poll_seconds
  if [ "$delay" -gt "$remaining" ]; then delay=$remaining; fi
  echo "Still waiting for: ${pending[*]}. Checking again in $delay seconds."
  sleep "$delay"
done
